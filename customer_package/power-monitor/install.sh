#!/bin/bash
################################################################################
# Power Monitor - Customer Installation Script
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║           POWER MONITOR - INSTALLATION                       ║
║                                                               ║
║     24/7 EB & Generator Monitoring System                    ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERROR: Please run as root (use sudo)${NC}"
    exit 1
fi

ACTUAL_USER=${SUDO_USER:-$USER}
INSTALL_DIR="/opt/power-monitor"
USER_HOME=$(eval echo ~$ACTUAL_USER)

echo -e "${GREEN}Installing Power Monitor...${NC}"
echo ""

# Step 1: Create installation directory
echo -e "${BLUE}[1/9]${NC} Creating installation directory..."
mkdir -p "$INSTALL_DIR"
cp -r . "$INSTALL_DIR/"
chown -R $ACTUAL_USER:$ACTUAL_USER "$INSTALL_DIR"
echo -e "${GREEN}✓${NC} Installed to: $INSTALL_DIR"

# Step 2: Install system dependencies
echo -e "${BLUE}[2/9]${NC} Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3-pip python3-tk mysql-server > /dev/null 2>&1
echo -e "${GREEN}✓${NC} System dependencies installed"

# Step 3: Install Python packages
echo -e "${BLUE}[3/9]${NC} Installing Python packages..."
pip3 install -q -r "$INSTALL_DIR/requirements.txt"
pip3 install -q RPi.GPIO twilio python-dotenv
echo -e "${GREEN}✓${NC} Python packages installed"

# Step 4: Run MySQL configuration wizard
echo -e "${BLUE}[4/9]${NC} Configuring MySQL..."
python3 "$INSTALL_DIR/configure_mysql.py"
echo -e "${GREEN}✓${NC} MySQL configured"

# Step 5: Setup configuration
echo -e "${BLUE}[5/9]${NC} Setting up application configuration..."
if [ ! -f "$INSTALL_DIR/config.json" ]; then
    cp "$INSTALL_DIR/config.example.json" "$INSTALL_DIR/config.json"
    chown $ACTUAL_USER:$ACTUAL_USER "$INSTALL_DIR/config.json"
fi
echo -e "${GREEN}✓${NC} Configuration ready"

# Step 6: Install service
echo -e "${BLUE}[6/9]${NC} Installing background service..."
cat > /etc/systemd/system/power-monitor.service << EOF
[Unit]
Description=Power Monitor Service - 24/7 EB and Generator Monitoring
After=network.target mysql.service

[Service]
Type=simple
User=$ACTUAL_USER
Group=$ACTUAL_USER
WorkingDirectory=$INSTALL_DIR
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 -m src.background_monitor
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable power-monitor.service > /dev/null 2>&1
systemctl start power-monitor.service
echo -e "${GREEN}✓${NC} Service installed and started"

# Step 7: Create desktop shortcut
echo -e "${BLUE}[7/9]${NC} Creating desktop shortcut..."
DESKTOP_DIR="$USER_HOME/Desktop"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/PowerMonitor.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Power Monitor
Comment=Power Monitoring Dashboard
Exec=python3 $INSTALL_DIR/src/main.pyc
Icon=utilities-system-monitor
Path=$INSTALL_DIR
Terminal=false
Categories=Utility;System;Monitor;
EOF
chmod +x "$DESKTOP_DIR/PowerMonitor.desktop"
chown $ACTUAL_USER:$ACTUAL_USER "$DESKTOP_DIR/PowerMonitor.desktop"
echo -e "${GREEN}✓${NC} Desktop shortcut created"

# Step 8: Create menu entry
echo -e "${BLUE}[8/9]${NC} Creating application menu entry..."
APPS_DIR="$USER_HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/power-monitor.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Power Monitor
Comment=Power Monitoring Dashboard
Exec=python3 $INSTALL_DIR/src/main.pyc
Icon=utilities-system-monitor
Path=$INSTALL_DIR
Terminal=false
Categories=Utility;System;Monitor;
EOF
chmod +x "$APPS_DIR/power-monitor.desktop"
chown $ACTUAL_USER:$ACTUAL_USER "$APPS_DIR/power-monitor.desktop"
echo -e "${GREEN}✓${NC} Menu entry created"

# Step 9: Set permissions
echo -e "${BLUE}[9/9]${NC} Setting permissions..."
usermod -a -G gpio $ACTUAL_USER > /dev/null 2>&1 || true
chmod -R 755 "$INSTALL_DIR"
echo -e "${GREEN}✓${NC} Permissions configured"

echo ""
echo -e "${GREEN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║              INSTALLATION COMPLETED!                          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo -e "${GREEN}Installation Summary:${NC}"
echo ""
echo "  ✓ Background Service (24/7 monitoring)"
echo "  ✓ Desktop GUI Application"
echo "  ✓ Desktop Shortcut"
echo "  ✓ Application Menu Entry"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "  1. Wire GPIO connections (see GPIO_WIRING.txt)"
echo "  2. Configure WhatsApp notifications (optional):"
echo "     sudo nano $INSTALL_DIR/.env"
echo "  3. Restart service:"
echo "     sudo systemctl restart power-monitor"
echo "  4. Open GUI: Double-click desktop icon"
echo ""
echo -e "${GREEN}Installation location: $INSTALL_DIR${NC}"
echo ""
