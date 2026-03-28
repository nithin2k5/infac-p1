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


class BackgroundMonitor:
    """Background service for 24/7 power monitoring."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize background monitor.
        
        Args:
            config_path: Path to configuration file (optional)
        """
        # Load configuration
        self.config = Config(config_path)
        
        # Setup logging
        self._setup_logging()
        
        # Initialize database writer
        db_config = self.config.get_database_config()
        self.db_writer = DatabaseWriter(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 3306),
            user=db_config.get("user", "root"),
            password=db_config.get("password", ""),
            database=db_config.get("database", "ebpc")
        )
        
        # Initialize GPIO reader
        self.gpio_reader = GPIOReader(
            on_state_change=self._handle_state_change,
            poll_interval=0.5,
            debounce_time=0.1
        )

        # Status LED: HIGH = service running, LOW = stopped/crashed
        status_pin = self.config.get("gpio.status_pin", StatusLED.DEFAULT_PIN)
        self.status_led = StatusLED(pin=int(status_pin))

        # Initialize Email sender
        self.email = EmailSender(self.config)
        
        # State tracking
        self.running: bool = False
        self.start_time: Optional[datetime] = None
        self.eb_outage_start_time: Optional[float] = None
        self.current_outage_id: Optional[int] = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Background monitor initialized")
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        log_level = logging.INFO
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('monitor_service.log', mode='a')
            ]
        )
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def _handle_state_change(self, input_id: str, state: int, timestamp: float) -> None:
        """
        Handle state change from GPIO reader.
        
        Args:
            input_id: Input identifier ('eb', 'gen1', 'gen2')
            state: New state (0=OFF, 1=ON)
            timestamp: Unix timestamp of change
        """
        try:
            # Get input name
            input_names = {
                'eb': 'EB (Electricity Board)',
                'gen1': 'Generator 1',
                'gen2': 'Generator 2'
            }
            input_name = input_names.get(input_id, input_id.upper())
            
            logger.info(
                f"State change: {input_name} -> {'ON' if state == 1 else 'OFF'} "
                f"at {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Record event in database
            event_id = self.db_writer.record_event(
                input_id=input_id,
                input_name=input_name,
                state=state,
                timestamp=timestamp
            )
            
            if event_id:
                logger.info(f"Event recorded with ID: {event_id}")
            else:
                logger.error("Failed to record event in database")
            
            # Check for power outage (EB went OFF)
            if input_id == 'eb' and state == 0:
                logger.warning("⚠️ POWER OUTAGE DETECTED - EB went OFF")
                self._handle_power_outage(timestamp)
            
            # Check for power restoration (EB came back ON)
            elif input_id == 'eb' and state == 1:
                logger.info("✓ POWER RESTORED - EB is back ON")
                self._handle_power_restored(timestamp)
            
            # Check for generator activation
            elif input_id in ['gen1', 'gen2'] and state == 1:
                self._handle_generator_activation(input_id, timestamp)
            
        except Exception as e:
            logger.error(f"Error handling state change: {e}", exc_info=True)
    
    def start(self) -> None:
        """Start the background monitoring service."""
        if self.running:
            logger.warning("Monitor already running")
            return
        
        logger.info("=" * 60)
        logger.info("Starting Background Power Monitor Service")
        logger.info("=" * 60)
        
        self.running = True
        self.start_time = datetime.now()
        
        # Test database connection
        if not self.db_writer.test_connection():
            logger.error("Cannot connect to database. Please check configuration.")
            self.running = False
            return
        
        logger.info("Database connection successful")
        
        # Display pin configuration
        logger.info("\nGPIO Pin Configuration:")
        for input_id, info in self.gpio_reader.get_pin_config().items():
            logger.info(f"  {input_id.upper()}: GPIO Pin {info['pin']} - {info['name']}")
        
        # Start GPIO monitoring
        self.gpio_reader.start_monitoring()

        # Signal that service is running
        self.status_led.on()
        logger.info(f"Status LED ON (GPIO {self.status_led.pin})")
        
        logger.info("\n✓ Monitor service started successfully")
        logger.info("Monitoring power status 24/7...")
        logger.info("Press Ctrl+C to stop\n")
        
        # Keep the main thread alive
        try:
            while self.running:
                time.sleep(1)
                
                # Periodic status update (every hour)
                if int(time.time()) % 3600 == 0:
                    st = self.start_time
                    if st:
                        uptime = datetime.now() - st
                        logger.info(f"Service running - Uptime: {uptime}")
                    
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stop the monitoring service."""
        if not self.running:
            return
        
        logger.info("Stopping background monitor service...")
        self.running = False
        
        # Turn off status LED first so it goes LOW even if cleanup crashes
        self.status_led.cleanup()

        # Stop GPIO monitoring
        self.gpio_reader.cleanup()

        # Close database connection
        self.db_writer.close()
        
        st = self.start_time
        if st:
            uptime = datetime.now() - st
            logger.info(f"Service stopped. Total uptime: {uptime}")
        
        logger.info("Background monitor service stopped")
    
    def _handle_power_outage(self, timestamp: float) -> None:
        """Handle EB power outage."""
        self.eb_outage_start_time = timestamp
        try:
            self.current_outage_id = self.db_writer.insert_outage(timestamp)
            logger.warning(f"Power outage recorded at timestamp: {timestamp} (Outage ID: {self.current_outage_id})")
        except Exception as e:
            logger.error(f"Failed to record outage in database: {e}")
            self.current_outage_id = None
            logger.warning(f"Power outage recorded at timestamp: {timestamp}")
    
    def _handle_power_restored(self, timestamp: float) -> None:
        """Handle EB power restoration."""
        eb_start = self.eb_outage_start_time
        if eb_start:
            duration = timestamp - eb_start
            logger.info(f"Power restored after {duration:.0f} seconds")
            
            if self.current_outage_id:
                try:
                    self.db_writer.update_outage_end(self.current_outage_id, timestamp, duration)
                except Exception as e:
                    logger.error(f"Failed to update outage end in database: {e}")
            
            self.eb_outage_start_time = None
            self.current_outage_id = None
    
    def _handle_generator_activation(self, generator_id: str, timestamp: float) -> None:
        """Handle generator activation and send Email notification."""
        eb_start = self.eb_outage_start_time
        if not eb_start:
            # Generator turned on but no outage recorded
            return
        
        # Calculate interval time (power cut to generator ON)
        interval_seconds = timestamp - eb_start
        
        generator_names = {
            'gen1': 'Generator 1 (GEN1)',
            'gen2': 'Generator 2 (GEN2)'
        }
        generator_name = generator_names.get(generator_id, generator_id.upper())
        
        logger.info(
            f"{generator_name} activated {interval_seconds:.1f} seconds after power cut"
        )
        
        # Send Email notification
        notification_sent = False
        try:
            notification_sent = self.email.send_generator_activation_notification(
                generator_name=generator_name,
                outage_start_time=eb_start,
                generator_start_time=timestamp
            )
            
            # Update outage record with generator info and notification status
            if self.current_outage_id:
                try:
                    self.db_writer.update_outage_generator(
                        self.current_outage_id, 
                        generator_id, 
                        timestamp,
                        notification_sent=notification_sent
                    )
                except Exception as e:
                    logger.error(f"Failed to update outage generator in database: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to send Email notification: {e}")
    
    def get_status(self) -> dict:
        """Get current service status."""
        st = self.start_time
        return {
            'running': self.running,
            'start_time': st.isoformat() if st else None,
            'uptime': str(datetime.now() - st) if st else None,
            'pin_config': self.gpio_reader.get_pin_config(),
            'email_enabled': self.email.enabled
        }


def main():
    """Main entry point for background monitor service."""
    print("Raspberry Pi Power Monitor - Background Service")
    print("=" * 60)
    
    try:
        monitor = BackgroundMonitor()
        monitor.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

