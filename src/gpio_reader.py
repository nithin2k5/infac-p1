"""GPIO reader module for Raspberry Pi to read power status from GPIO pins."""
import logging
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import threading

logger = logging.getLogger(__name__)

# Try to import RPi.GPIO
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("RPi.GPIO not available. GPIO reading will be simulated.")


class GPIOReader:
    """Read power status from Raspberry Pi GPIO pins."""
    
    # GPIO Pin assignments
    PIN_EB = 17      # GPIO 17 (Pin 11) - EB power status
    PIN_GEN1 = 27    # GPIO 27 (Pin 13) - Generator 1 status
    PIN_GEN2 = 22    # GPIO 22 (Pin 15) - Generator 2 status
    
    def __init__(
        self,
        on_state_change: Optional[Callable[[str, int, float], None]] = None,
        poll_interval: float = 0.5,
        debounce_time: float = 0.1
    ):
        """
        Initialize GPIO reader.
        
        Args:
            on_state_change: Callback function(input_id, state, timestamp) called when state changes
            poll_interval: Polling interval in seconds (default: 0.5s)
            debounce_time: Debounce time in seconds to avoid false triggers (default: 0.1s)
        """
        self.on_state_change = on_state_change
        self.poll_interval = poll_interval
        self.debounce_time = debounce_time
        
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
            }
        }
        
        self.running = False
        self.monitor_thread = None
        
        # Initialize GPIO if available
        if not GPIO_AVAILABLE:
            raise ImportError(
                "RPi.GPIO not available. This module requires Raspberry Pi hardware. "
                "Install with: pip3 install RPi.GPIO"
            )
        
        self._setup_gpio()
    
    def _setup_gpio(self) -> None:
        """Setup GPIO pins for reading."""
        try:
            # Set GPIO mode to BCM (Broadcom chip-specific pin numbers)
            GPIO.setmode(GPIO.BCM)
            
            # Disable warnings
            GPIO.setwarnings(False)
            
            # Setup pins as INPUT with pull-down resistors
            # When power is ON, pin will be HIGH (1)
            # When power is OFF, pin will be LOW (0)
            for input_id, config in self.pin_config.items():
                pin = config['pin']
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                logger.info(f"Configured GPIO pin {pin} for {config['name']}")
            
            logger.info("GPIO setup completed successfully")
            
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
            logger.error("RPi.GPIO not available. This module requires Raspberry Pi hardware.")
            return None
        
        config = self.pin_config[input_id]
        pin = config['pin']
        
        try:
            # Read actual GPIO pin
            state = GPIO.input(pin)
            return 1 if state == GPIO.HIGH else 0
                
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
                GPIO.cleanup()
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

