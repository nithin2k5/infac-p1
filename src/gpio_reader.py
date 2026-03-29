"""GPIO reader module for Raspberry Pi to read power status from GPIO pins."""
import logging
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import threading

logger = logging.getLogger(__name__)

GPIO = None
GPIO_AVAILABLE = False
GPIO_BACKEND = None

try:
    import gpiod
    GPIO_AVAILABLE = True
    GPIO_BACKEND = "gpiod"
except ImportError:
    try:
        import lgpio
        GPIO_AVAILABLE = True
        GPIO_BACKEND = "lgpio"
    except ImportError:
        try:
            import RPi.GPIO as GPIO
            GPIO_AVAILABLE = True
            GPIO_BACKEND = "RPi.GPIO"
        except (ImportError, RuntimeError):
            GPIO_AVAILABLE = False
            logger.warning("No GPIO library available")


class GPIOReader:
    """Read power status from Raspberry Pi GPIO pins."""
    
    # GPIO Pin assignments
    PIN_EB   = 17    # GPIO 17 (Pin 11) - EB power status
    PIN_GEN1 = 27    # GPIO 27 (Pin 13) - Generator 1 status
    PIN_GEN2 = 22    # GPIO 22 (Pin 15) - Generator 2 status
    PIN_GEN3 = 23    # GPIO 23 (Pin 16) - Generator 3 status
    
    # Default reason pins (BCM GPIO numbers)
    PIN_REASON_EXT   = 5    # GPIO 5  (Pin 29) - External Power Cut
    PIN_REASON_TRIP  = 6    # GPIO 6  (Pin 31) - Internal Trip
    PIN_REASON_FUSE  = 13   # GPIO 13 (Pin 33) - Fuse Blown

    def __init__(
        self,
        on_state_change: Optional[Callable[[str, int, float], None]] = None,
        poll_interval: float = 0.5,
        debounce_time: float = 0.1,
        reason_pins: Optional[Dict[str, int]] = None
    ):
        """
        Initialize GPIO reader.

        Args:
            on_state_change: Callback(input_id, state, timestamp) called on state changes
            poll_interval: Polling interval in seconds (default 0.5s)
            debounce_time: Debounce time in seconds (default 0.1s)
            reason_pins: Optional dict mapping reason key → GPIO pin number.
                Keys: 'reason_ext', 'reason_trip', 'reason_fuse'
        """
        self.on_state_change = on_state_change
        self.poll_interval = poll_interval
        self.debounce_time = debounce_time

        _rp = reason_pins or {}

        # Pin configuration
        self.pin_config = {
            'eb': {
                'pin': self.PIN_EB,
                'name': 'EB (Electricity Board)',
                'last_state': None,
                'last_change_time': 0
            },
            'gen1': {
                'pin': self.PIN_GEN1,
                'name': 'Generator 1',
                'last_state': None,
                'last_change_time': 0
            },
            'gen2': {
                'pin': self.PIN_GEN2,
                'name': 'Generator 2',
                'last_state': None,
                'last_change_time': 0
            },
            'gen3': {
                'pin': self.PIN_GEN3,
                'name': 'Generator 3',
                'last_state': None,
                'last_change_time': 0
            },
            'reason_ext': {
                'pin': _rp.get('reason_ext', self.PIN_REASON_EXT),
                'name': 'Reason: External Power Cut',
                'last_state': None,
                'last_change_time': 0
            },
            'reason_trip': {
                'pin': _rp.get('reason_trip', self.PIN_REASON_TRIP),
                'name': 'Reason: Internal Trip',
                'last_state': None,
                'last_change_time': 0
            },
            'reason_fuse': {
                'pin': _rp.get('reason_fuse', self.PIN_REASON_FUSE),
                'name': 'Reason: Fuse Blown',
                'last_state': None,
                'last_change_time': 0
            },
        }
        
        self.running = False
        self.monitor_thread = None
        self.gpio_backend = GPIO_BACKEND
        self.chip = None
        self.lines = None
        
        if not GPIO_AVAILABLE:
            raise ImportError(
                "No GPIO library available. For Raspberry Pi 5, install: pip3 install gpiod"
            )
        
        self._setup_gpio()
    
    def _setup_gpio(self) -> None:
        """Setup GPIO pins for reading."""
        try:
            if GPIO_BACKEND == "RPi.GPIO":
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                for input_id, config in self.pin_config.items():
                    pin = config['pin']
                    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                    logger.info(f"Configured GPIO pin {pin} for {config['name']}")
                    
            elif GPIO_BACKEND == "gpiod":
                import gpiod
                self.chip = gpiod.Chip('/dev/gpiochip4')
                self.lines = {}
                pins = {v['pin'] for v in self.pin_config.values()}
                line_req = self.chip.request_lines(
                    consumer="power-monitor",
                    config={
                        (pin,): gpiod.LineSettings(
                            direction=gpiod.line.Direction.INPUT,
                            bias=gpiod.line.Bias.PULL_DOWN
                        ) for pin in pins
                    }
                )
                for input_id, config in self.pin_config.items():
                    self.lines[input_id] = {'req': line_req, 'pin': config['pin']}
                    logger.info(f"Configured GPIO pin {config['pin']} for {config['name']} (gpiod v2)")
                    
            elif GPIO_BACKEND == "lgpio":
                import lgpio
                self.chip = lgpio.gpiochip_open(4)
                for input_id, config in self.pin_config.items():
                    pin = config['pin']
                    lgpio.gpio_claim_input(self.chip, pin, lgpio.SET_PULL_DOWN)
                    logger.info(f"Configured GPIO pin {pin} for {config['name']} (lgpio)")
            
            logger.info(f"GPIO setup completed successfully using {GPIO_BACKEND}")
            
        except Exception as e:
            logger.error(f"Error setting up GPIO: {e}")
            raise
    
    def read_pin(self, input_id: str) -> Optional[int]:
        """
        Read current state of a GPIO pin.
        
        Args:
            input_id: Input identifier ('eb', 'gen1', 'gen2')
            
        Returns:
            1 for HIGH (ON), 0 for LOW (OFF), None if error
        """
        if input_id not in self.pin_config:
            logger.error(f"Invalid input_id: {input_id}")
            return None
        
        if not GPIO_AVAILABLE:
            logger.error("No GPIO library available")
            return None
        
        config = self.pin_config[input_id]
        pin = config['pin']
        
        try:
            if GPIO_BACKEND == "RPi.GPIO":
                state = GPIO.input(pin)
                return 1 if state == GPIO.HIGH else 0
                
            elif GPIO_BACKEND == "gpiod":
                line_info = self.lines[input_id]
                state = line_info['req'].get_value(line_info['pin'])
                return 1 if state.value == 1 else 0
                
            elif GPIO_BACKEND == "lgpio":
                import lgpio
                state = lgpio.gpio_read(self.chip, pin)
                return 1 if state == 1 else 0
                
        except Exception as e:
            logger.error(f"Error reading GPIO pin {pin} for {input_id}: {e}")
            return None
    
    def read_all_pins(self) -> Dict[str, int]:
        """
        Read all configured GPIO pins.
        
        Returns:
            Dictionary mapping input_id to state (0 or 1)
        """
        states = {}
        for input_id in self.pin_config.keys():
            state = self.read_pin(input_id)
            if state is not None:
                states[input_id] = state
        return states
    
    def start_monitoring(self) -> None:
        """Start continuous monitoring of GPIO pins."""
        if self.running:
            logger.warning("Monitoring already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("GPIO monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop monitoring GPIO pins."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        logger.info("GPIO monitoring stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop that polls GPIO pins."""
        logger.info("GPIO monitor loop started")
        
        while self.running:
            try:
                current_time = time.time()
                
                # Read all pins
                for input_id, config in self.pin_config.items():
                    state = self.read_pin(input_id)
                    
                    if state is None:
                        continue
                    
                    last_state = config['last_state']
                    last_change_time = config['last_change_time']
                    
                    # Check if state changed
                    if last_state is not None and state != last_state:
                        # Debounce: only trigger if enough time has passed since last change
                        if current_time - last_change_time >= self.debounce_time:
                            logger.info(
                                f"State change detected: {config['name']} "
                                f"{'OFF' if last_state == 1 else 'ON'} -> "
                                f"{'ON' if state == 1 else 'OFF'}"
                            )
                            
                            # Update state
                            config['last_state'] = state
                            config['last_change_time'] = current_time
                            
                            # Trigger callback
                            if self.on_state_change:
                                try:
                                    self.on_state_change(input_id, state, current_time)
                                except Exception as e:
                                    logger.error(f"Error in state change callback: {e}")
                    
                    elif last_state is None:
                        # First reading - initialize state
                        config['last_state'] = state
                        config['last_change_time'] = current_time
                        logger.info(f"Initial state for {config['name']}: {'ON' if state == 1 else 'OFF'}")
                        
                        # Trigger callback for initial state
                        if self.on_state_change:
                            try:
                                self.on_state_change(input_id, state, current_time)
                            except Exception as e:
                                logger.error(f"Error in state change callback: {e}")
                
                # Sleep before next poll
                time.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                time.sleep(1.0)  # Sleep longer on error
        
        logger.info("GPIO monitor loop ended")
    
    def cleanup(self) -> None:
        """Cleanup GPIO resources."""
        self.stop_monitoring()
        
        if GPIO_AVAILABLE:
            try:
                if GPIO_BACKEND == "RPi.GPIO":
                    GPIO.cleanup()
                elif GPIO_BACKEND == "gpiod":
                    released = False
                    if self.lines:
                        for line_info in self.lines.values():
                            if not released:
                                try:
                                    line_info['req'].release()
                                    released = True
                                except Exception:
                                    pass
                    if self.chip:
                        self.chip.close()
                elif GPIO_BACKEND == "lgpio":
                    import lgpio
                    if self.chip is not None:
                        lgpio.gpiochip_close(self.chip)
                logger.info("GPIO cleanup completed")
            except Exception as e:
                logger.error(f"Error during GPIO cleanup: {e}")
    
    def get_pin_config(self) -> Dict[str, Any]:
        """Get current pin configuration."""
        return {
            input_id: {
                'pin': config['pin'],
                'name': config['name'],
                'current_state': config['last_state']
            }
            for input_id, config in self.pin_config.items()
        }


class StatusLED:
    """
    Controls a single GPIO output pin as a service status indicator.
    HIGH when service is running, LOW when stopped or crashed.
    Default pin: GPIO 24 (physical Pin 18).
    """

    DEFAULT_PIN = 24

    def __init__(self, pin: int = DEFAULT_PIN):
        self.pin = pin
        self._chip = None
        self._req = None
        self._available = GPIO_AVAILABLE
        self._setup()

    def _setup(self) -> None:
        if not self._available:
            return
        try:
            if GPIO_BACKEND == "RPi.GPIO":
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                GPIO.setup(self.pin, GPIO.OUT, initial=GPIO.LOW)

            elif GPIO_BACKEND == "gpiod":
                import gpiod
                self._chip = gpiod.Chip('/dev/gpiochip4')
                self._req = self._chip.request_lines(
                    consumer="power-monitor-status",
                    config={
                        (self.pin,): gpiod.LineSettings(
                            direction=gpiod.line.Direction.OUTPUT,
                            output_value=gpiod.line.Value.INACTIVE
                        )
                    }
                )

            elif GPIO_BACKEND == "lgpio":
                import lgpio
                self._chip = lgpio.gpiochip_open(4)
                lgpio.gpio_claim_output(self._chip, self.pin, 0)

            logger.info(f"Status LED configured on GPIO {self.pin} ({GPIO_BACKEND})")
        except Exception as e:
            logger.warning(f"Status LED setup failed (non-fatal): {e}")
            self._available = False

    def on(self) -> None:
        if not self._available:
            return
        try:
            if GPIO_BACKEND == "RPi.GPIO":
                GPIO.output(self.pin, GPIO.HIGH)
            elif GPIO_BACKEND == "gpiod" and self._req:
                import gpiod
                self._req.set_value(self.pin, gpiod.line.Value.ACTIVE)
            elif GPIO_BACKEND == "lgpio" and self._chip is not None:
                import lgpio
                lgpio.gpio_write(self._chip, self.pin, 1)
        except Exception as e:
            logger.warning(f"Status LED on() failed: {e}")

    def off(self) -> None:
        if not self._available:
            return
        try:
            if GPIO_BACKEND == "RPi.GPIO":
                GPIO.output(self.pin, GPIO.LOW)
            elif GPIO_BACKEND == "gpiod" and self._req:
                import gpiod
                self._req.set_value(self.pin, gpiod.line.Value.INACTIVE)
            elif GPIO_BACKEND == "lgpio" and self._chip is not None:
                import lgpio
                lgpio.gpio_write(self._chip, self.pin, 0)
        except Exception as e:
            logger.warning(f"Status LED off() failed: {e}")

    def cleanup(self) -> None:
        self.off()
        try:
            if GPIO_BACKEND == "gpiod" and self._req:
                self._req.release()
            if GPIO_BACKEND == "gpiod" and self._chip:
                self._chip.close()
            if GPIO_BACKEND == "lgpio" and self._chip is not None:
                import lgpio
                lgpio.gpiochip_close(self._chip)
        except Exception:
            pass


# Standalone test function
def test_gpio_reader():
    """Test GPIO reader functionality."""
    print("GPIO Reader Test")
    print("=" * 50)
    
    def on_change(input_id, state, timestamp):
        dt = datetime.fromtimestamp(timestamp)
        state_str = "ON" if state == 1 else "OFF"
        print(f"[{dt.strftime('%H:%M:%S')}] {input_id.upper()}: {state_str}")
    
    reader = GPIOReader(on_state_change=on_change, poll_interval=0.5)
    
    try:
        print("\nPin Configuration:")
        for input_id, info in reader.get_pin_config().items():
            print(f"  {input_id.upper()}: GPIO Pin {info['pin']} - {info['name']}")
        
        print("\nStarting monitoring... (Press Ctrl+C to stop)")
        reader.start_monitoring()
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        reader.cleanup()
        print("Test completed")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    test_gpio_reader()

