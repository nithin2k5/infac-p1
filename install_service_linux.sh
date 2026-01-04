#!/bin/bash
# Linux/Raspberry Pi Service Installation Script for Power Monitor
# This script sets up the application to run 24/7 as a systemd service

echo "========================================"
echo "Power Monitor - Linux Service Setup"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Get the actual user who called sudo
ACTUAL_USER=${SUDO_USER:-$USER}
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Installing Python dependencies..."
pip3 install -r requirements.txt
pip3 install RPi.GPIO

echo ""
echo "Creating systemd service..."

# Update the service file with correct paths
SERVICE_FILE="/etc/systemd/system/power-monitor.service"
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Power Monitor Service - 24/7 EB and Generator Monitoring
After=network.target mysql.service

[Service]
Type=simple
User=$ACTUAL_USER
Group=$ACTUAL_USER
WorkingDirectory=$SCRIPT_DIR
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 -m src.background_monitor
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Restart policy
StartLimitInterval=200
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
EOF

echo "Service file created at: $SERVICE_FILE"

# Reload systemd
echo ""
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable service to start on boot
echo "Enabling service to start on boot..."
systemctl enable power-monitor.service

# Start the service
echo "Starting the service..."
systemctl start power-monitor.service

echo ""
echo "========================================"
echo "Service installed successfully!"
echo "========================================"
echo ""
echo "The monitor will now run 24/7 in the background."
echo ""
echo "Useful commands:"
echo "  - Check status:    sudo systemctl status power-monitor"
echo "  - View logs:       sudo journalctl -u power-monitor -f"
echo "  - Stop service:    sudo systemctl stop power-monitor"
echo "  - Start service:   sudo systemctl start power-monitor"
echo "  - Restart service: sudo systemctl restart power-monitor"
echo "  - Disable service: sudo systemctl disable power-monitor"
echo ""
echo "Checking service status..."
systemctl status power-monitor.service --no-pager

