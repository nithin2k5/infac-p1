"""Windows Service installer for Power Monitor."""
import sys
import os

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    import socket
except ImportError:
    print("ERROR: pywin32 not installed. Install with: pip install pywin32")
    sys.exit(1)

import logging
from pathlib import Path


class PowerMonitorService(win32serviceutil.ServiceFramework):
    """Windows Service for Power Monitor."""
    
    _svc_name_ = "PowerMonitorService"
    _svc_display_name_ = "Power Monitor Service"
    _svc_description_ = "24/7 monitoring service for EB and Generator power status"
    
    def __init__(self, args):
        """Initialize the service."""
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        
        # Setup logging
        log_path = Path(__file__).parent / "service.log"
        logging.basicConfig(
            filename=str(log_path),
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def SvcStop(self):
        """Stop the service."""
        self.logger.info("Service stop requested")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.running = False
    
    def SvcDoRun(self):
        """Run the service."""
        self.logger.info("Service starting...")
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        try:
            self.main()
        except Exception as e:
            self.logger.error(f"Service error: {e}", exc_info=True)
            servicemanager.LogErrorMsg(f"Service error: {e}")
    
    def main(self):
        """Main service logic."""
        self.logger.info("Initializing Power Monitor Service")
        
        # Import here to avoid issues during service installation
        from src.background_monitor import BackgroundMonitor
        
        try:
            # Create and start monitor
            monitor = BackgroundMonitor()
            self.logger.info("Starting background monitor...")
            
            # Start monitoring in a separate thread
            import threading
            monitor_thread = threading.Thread(target=monitor.start, daemon=False)
            monitor_thread.start()
            
            # Wait for stop event
            while self.running:
                # Check if stop event is set (with 1 second timeout)
                rc = win32event.WaitForSingleObject(self.stop_event, 1000)
                if rc == win32event.WAIT_OBJECT_0:
                    break
            
            # Stop the monitor
            self.logger.info("Stopping background monitor...")
            monitor.stop()
            
            self.logger.info("Service stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error in main service loop: {e}", exc_info=True)
            raise


if __name__ == '__main__':
    if len(sys.argv) == 1:
        # No arguments - try to start the service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PowerMonitorService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Handle command line arguments (install, remove, start, stop, etc.)
        win32serviceutil.HandleCommandLine(PowerMonitorService)

