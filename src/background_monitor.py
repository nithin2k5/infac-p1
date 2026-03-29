"""Background monitoring service that runs 24/7 to monitor power status."""
import logging
import time
import signal
import sys
from datetime import datetime
from typing import Optional
import threading

from .config import Config  # type: ignore
from .gpio_reader import GPIOReader, StatusLED  # type: ignore
from .db_writer import DatabaseWriter  # type: ignore
from .email_sender import EmailSender  # type: ignore

logger = logging.getLogger(__name__)


def _empty_outage() -> dict:
    return {
        'eb_off_time':  None,
        'eb_on_time':   None,
        'gen1': {'on': None, 'off': None},
        'gen2': {'on': None, 'off': None},
        'gen3': {'on': None, 'off': None},
        'reason':       None,
    }


class BackgroundMonitor:
    """Background service for 24/7 power monitoring."""

    def __init__(self, config_path: Optional[str] = None):
        self.config = Config(config_path)
        self._setup_logging()

        db_config = self.config.get_database_config()
        self.db_writer = DatabaseWriter(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 3306),
            user=db_config.get("user", "root"),
            password=db_config.get("password", ""),
            database=db_config.get("database", "ebpc")
        )

        gpio_cfg = self.config.get("gpio", {}) or {}
        poll_interval  = float(gpio_cfg.get("poll_interval", 0.5))
        debounce_time  = float(gpio_cfg.get("debounce_time", 0.1))

        rp_cfg = gpio_cfg.get("reason_pins", {})
        reason_pins = {
            'reason_ext':  int(rp_cfg.get("external_power_cut", 5)),
            'reason_trip': int(rp_cfg.get("internal_trip",       6)),
            'reason_fuse': int(rp_cfg.get("fuse_blown",          13)),
        }

        self.gpio_reader = GPIOReader(
            on_state_change=self._handle_state_change,
            poll_interval=poll_interval,
            debounce_time=debounce_time,
            reason_pins=reason_pins,
        )

        status_pin = self.config.get("gpio.status_pin", StatusLED.DEFAULT_PIN)
        self.status_led = StatusLED(pin=int(status_pin))

        self.email = EmailSender(self.config)

        # Runtime state
        self.running: bool = False
        self.start_time: Optional[datetime] = None

        # Tracks live GPIO states for all inputs
        self.current_states: dict = {
            'eb': None, 'gen1': None, 'gen2': None, 'gen3': None,
            'reason_ext': None, 'reason_trip': None, 'reason_fuse': None,
        }

        # Full outage event being tracked
        self._outage: dict = _empty_outage()
        self._outage_active: bool = False
        self._outage_email_sent: bool = False

        # After EB restores: 60s window for reason pins; else email with "to be updated"
        self._awaiting_reason_after_restore: bool = False
        self._pending_email_timer: Optional[threading.Timer] = None

        # Legacy outage DB tracking
        self.current_outage_id: Optional[int] = None

        signal.signal(signal.SIGINT,  self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("Background monitor initialized")

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _setup_logging(self) -> None:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('monitor_service.log', mode='a')
            ]
        )

    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down…")
        self.stop()
        sys.exit(0)

    def _cancel_pending_timer(self) -> None:
        if self._pending_email_timer:
            self._pending_email_timer.cancel()
            self._pending_email_timer = None

    # ──────────────────────────────────────────────────────────────────────────
    # GPIO state-change handler
    # ──────────────────────────────────────────────────────────────────────────

    def _handle_state_change(self, input_id: str, state: int, timestamp: float) -> None:
        try:
            input_names = {
                'eb':           'EB (Electricity Board)',
                'gen1':         'Generator 1',
                'gen2':         'Generator 2',
                'gen3':         'Generator 3',
                'reason_ext':   'Reason: External Power Cut',
                'reason_trip':  'Reason: Internal Trip',
                'reason_fuse':  'Reason: Fuse Blown',
            }
            input_name = input_names.get(input_id, input_id.upper())

            logger.info(
                f"State change: {input_name} → {'ON' if state == 1 else 'OFF'} "
                f"at {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}"
            )

            self.current_states[input_id] = state

            # ── Reason pins (never stored in DB; email only after EB restore) ─
            if input_id in ('reason_ext', 'reason_trip', 'reason_fuse'):
                if (
                    state == 1
                    and self._awaiting_reason_after_restore
                    and not self._outage_email_sent
                ):
                    reason_map = {
                        'reason_ext':  'External Power Cut',
                        'reason_trip': 'Internal Trip',
                        'reason_fuse': 'Fuse Blown',
                    }
                    self._outage['reason'] = reason_map[input_id]
                    logger.info(f"Reason pin HIGH — sending email: {self._outage['reason']}")
                    self._cancel_pending_timer()
                    self._send_outage_email(bypass_rate_limit=True)
                    self._outage_email_sent = True
                    self._awaiting_reason_after_restore = False
                return

            # ── DB event recording (only for power/generator inputs) ─────────
            event_id = self.db_writer.record_event(
                input_id=input_id,
                input_name=input_name,
                state=state,
                timestamp=timestamp
            )
            if event_id:
                logger.info(f"Event recorded ID={event_id}")
            else:
                logger.error("Failed to record event in database")

            # ── EB OFF → power cut detected (no email yet) ───────────────────
            if input_id == 'eb' and state == 0:
                logger.warning("POWER OUTAGE DETECTED — EB went OFF")
                self._cancel_pending_timer()
                self._awaiting_reason_after_restore = False
                self._outage = _empty_outage()
                self._outage['eb_off_time'] = timestamp
                self._outage_active = True
                self._outage_email_sent = False
                self._record_outage_start(timestamp)

            # ── EB ON → power restored: start 60s window for reason pins ─────
            elif input_id == 'eb' and state == 1:
                logger.info("POWER RESTORED — EB is back ON")
                self._cancel_pending_timer()
                if self._outage_active:
                    self._outage['eb_on_time'] = timestamp
                    self._record_outage_end(timestamp)
                    for g in ('gen1', 'gen2', 'gen3'):
                        if self._outage[g]['on'] and not self._outage[g]['off']:
                            self._outage[g]['off'] = timestamp
                    self._outage['reason'] = None
                    self._outage_email_sent = False
                    self._awaiting_reason_after_restore = True
                    t = threading.Timer(60.0, self._send_post_restore_timeout_email)
                    t.daemon = True
                    t.start()
                    self._pending_email_timer = t
                    logger.info("60s window started — press a reason pin or email sends as 'to be updated'")
                self._outage_active = False

            # ── Generator state change (DB only — no email) ─────────────────
            elif input_id in ('gen1', 'gen2', 'gen3'):
                if state == 1:
                    self._handle_generator_activation(input_id, timestamp)
                elif state == 0 and self._outage_active:
                    if not self._outage[input_id]['off']:
                        self._outage[input_id]['off'] = timestamp

        except Exception as e:
            logger.error(f"Error handling state change: {e}", exc_info=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Outage helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _record_outage_start(self, timestamp: float) -> None:
        try:
            self.current_outage_id = self.db_writer.insert_outage(timestamp)
            logger.warning(f"Outage recorded ID={self.current_outage_id}")
        except Exception as e:
            logger.error(f"Failed to record outage start: {e}")
            self.current_outage_id = None

    def _record_outage_end(self, timestamp: float) -> None:
        off_t = self._outage.get('eb_off_time')
        if off_t and self.current_outage_id:
            duration = timestamp - off_t
            try:
                self.db_writer.update_outage_end(self.current_outage_id, timestamp, duration)
            except Exception as e:
                logger.error(f"Failed to update outage end: {e}")
        self.current_outage_id = None

    def _handle_generator_activation(self, generator_id: str, timestamp: float) -> None:
        eb_start = self._outage.get('eb_off_time')
        if not eb_start:
            return
        if not self._outage[generator_id]['on']:
            self._outage[generator_id]['on'] = timestamp
        interval = timestamp - eb_start
        logger.info(f"{generator_id.upper()} activated {interval:.1f}s after power cut")
        if self.current_outage_id:
            try:
                self.db_writer.update_outage_generator(
                    self.current_outage_id, generator_id, timestamp, notification_sent=False
                )
            except Exception as e:
                logger.error(f"Failed to update outage generator: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # Email helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _send_outage_email(self, bypass_rate_limit: bool = False) -> None:
        try:
            self.email.send_outage_notification(
                outage=dict(self._outage),
                bypass_rate_limit=bypass_rate_limit
            )
        except Exception as e:
            logger.error(f"Failed to send outage email: {e}")

    def _send_post_restore_timeout_email(self) -> None:
        """Fired 60s after EB came back if no reason pin went HIGH."""
        self._pending_email_timer = None
        if self._outage_email_sent:
            return
        if not self._awaiting_reason_after_restore:
            return
        self._outage['reason'] = "to be updated"
        logger.info("60s after EB restore — no reason pin; sending email with 'to be updated'")
        self._send_outage_email(bypass_rate_limit=True)
        self._outage_email_sent = True
        self._awaiting_reason_after_restore = False

    # ──────────────────────────────────────────────────────────────────────────
    # Service lifecycle
    # ──────────────────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self.running:
            logger.warning("Monitor already running")
            return

        logger.info("=" * 60)
        logger.info("Starting Background Power Monitor Service")
        logger.info("=" * 60)

        self.running = True
        self.start_time = datetime.now()

        if not self.db_writer.test_connection():
            logger.error("Cannot connect to database. Check configuration.")
            self.running = False
            return

        logger.info("Database connection successful")

        logger.info("\nGPIO Pin Configuration:")
        for input_id, info in self.gpio_reader.get_pin_config().items():
            logger.info(f"  {input_id.upper()}: GPIO Pin {info['pin']} — {info['name']}")

        self.gpio_reader.start_monitoring()
        self.status_led.on()
        logger.info(f"Status LED ON (GPIO {self.status_led.pin})")
        logger.info("\n✓ Monitor service started — monitoring 24/7…\n")

        try:
            while self.running:
                time.sleep(1)
                if int(time.time()) % 3600 == 0:
                    st = self.start_time
                    if st:
                        logger.info(f"Service uptime: {datetime.now() - st}")
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()

    def stop(self) -> None:
        if not self.running:
            return
        logger.info("Stopping background monitor service…")
        self.running = False
        self._cancel_pending_timer()
        self.status_led.cleanup()
        self.gpio_reader.cleanup()
        self.db_writer.close()
        st = self.start_time
        if st:
            logger.info(f"Service stopped. Total uptime: {datetime.now() - st}")
        logger.info("Background monitor service stopped")

    def get_status(self) -> dict:
        st = self.start_time
        return {
            'running':       self.running,
            'start_time':    st.isoformat() if st else None,
            'uptime':        str(datetime.now() - st) if st else None,
            'pin_config':    self.gpio_reader.get_pin_config(),
            'email_enabled': self.email.enabled,
        }


def main():
    print("Raspberry Pi Power Monitor — Background Service")
    print("=" * 60)
    try:
        monitor = BackgroundMonitor()
        monitor.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
