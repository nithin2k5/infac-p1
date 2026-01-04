"""
Script to build Windows executables using PyInstaller.
Run this on Windows to create standalone .exe files.
"""
import os
import sys
import subprocess

def build_gui_exe():
    """Build GUI application executable."""
    print("Building GUI Application...")
    cmd = [
        'pyinstaller',
        '--onefile',
        '--windowed',
        '--name=PowerMonitorGUI',
        '--add-data=config.json;.',
        '--hidden-import=mysql.connector',
        '--hidden-import=pymysql',
        '--hidden-import=matplotlib',
        '--hidden-import=tkinter',
        'src/main.py'
    ]
    subprocess.run(cmd)

def build_service_exe():
    """Build service executable."""
    print("\nBuilding Service Application...")
    cmd = [
        'pyinstaller',
        '--onefile',
        '--name=PowerMonitorService',
        '--add-data=config.json;.',
        '--hidden-import=mysql.connector',
        '--hidden-import=pymysql',
        '--hidden-import=win32serviceutil',
        '--hidden-import=win32service',
        '--hidden-import=win32event',
        'run_monitor_service.py'
    ]
    subprocess.run(cmd)

def main():
    """Main build function."""
    print("=" * 60)
    print("Power Monitor - Windows Executable Builder")
    print("=" * 60)
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("\nERROR: PyInstaller not installed!")
        print("Install with: pip install pyinstaller")
        sys.exit(1)
    
    # Check if on Windows
    if sys.platform != 'win32':
        print("\nWARNING: This script is designed for Windows.")
        print("You can still build, but the .exe will only work on Windows.")
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)
    
    print("\nWhat would you like to build?")
    print("1. GUI Application only")
    print("2. Service Application only")
    print("3. Both (recommended)")
    print("4. Exit")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == '1':
        build_gui_exe()
    elif choice == '2':
        build_service_exe()
    elif choice == '3':
        build_gui_exe()
        build_service_exe()
    else:
        print("Exiting...")
        sys.exit(0)
    
    print("\n" + "=" * 60)
    print("Build Complete!")
    print("=" * 60)
    print("\nExecutables are in the 'dist' folder:")
    print("  - PowerMonitorGUI.exe (Desktop application)")
    print("  - PowerMonitorService.exe (Background service)")
    print("\nTo distribute:")
    print("  1. Copy .exe files from 'dist' folder")
    print("  2. Include config.json")
    print("  3. Include install_windows_service.py")
    print("  4. Include install_service_windows.bat")
    print("\nOn target machine:")
    print("  - Run install_service_windows.bat as Administrator")
    print("  - Or double-click PowerMonitorGUI.exe for GUI mode")

if __name__ == "__main__":
    main()

