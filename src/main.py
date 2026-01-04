"""Main entry point for the Raspberry Pi Monitor Desktop Application."""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Main entry point."""
    try:
        from src.monitor_gui import MonitorGUI
    except ImportError:
        from monitor_gui import MonitorGUI
    
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



