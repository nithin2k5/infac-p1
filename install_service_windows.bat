@echo off
REM Windows Service Installation Script for Power Monitor
REM This script sets up the application to run 24/7 as a Windows service

echo ========================================
echo Power Monitor - Windows Service Setup
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Right-click on this file and select "Run as administrator"
    pause
    exit /b 1
)

echo Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pywin32

echo.
echo Creating Windows service...
python install_windows_service.py install

echo.
echo Starting the service...
python install_windows_service.py start

echo.
echo ========================================
echo Service installed successfully!
echo ========================================
echo.
echo The monitor will now run 24/7 in the background.
echo.
echo Useful commands:
echo   - Start service:   python install_windows_service.py start
echo   - Stop service:    python install_windows_service.py stop
echo   - Remove service:  python install_windows_service.py remove
echo   - Check status:    sc query PowerMonitorService
echo.
pause

