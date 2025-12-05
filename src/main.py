"""Main entry point for the Raspberry Pi Monitor Desktop Application."""
import sys
import os

def main():
    """Main entry point."""
    from .monitor_gui import MonitorGUI
    
    try:
        app = MonitorGUI()
        app.run()
    except KeyboardInterrupt:
        print("\nShutdown requested")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()



