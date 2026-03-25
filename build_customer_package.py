#!/usr/bin/env python3
"""
Build customer distribution package without source code.
Creates a compiled version ready for deployment.
"""
import os
import sys
import shutil
import py_compile
import subprocess
from pathlib import Path

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore

# Colors for output
class Colors:
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'  # No Color

def print_header(text):
    print(f"{Colors.BLUE}{'='*70}{Colors.NC}")
    print(f"{Colors.BLUE}{text:^70}{Colors.NC}")
    print(f"{Colors.BLUE}{'='*70}{Colors.NC}")

def print_step(step, total, text):
    print(f"{Colors.BLUE}[{step}/{total}]{Colors.NC} {text}")

def print_success(text):
    print(f"{Colors.GREEN}[OK]{Colors.NC} {text}")

def print_error(text):
    print(f"{Colors.RED}[ERR]{Colors.NC} {text}")

def print_warning(text):
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {text}")

def compile_python_file(src_file, dest_dir):
    """Compile a Python file to bytecode."""
    try:
        # Compile to .pyc
        py_compile.compile(src_file, cfile=None, dfile=None, doraise=True, optimize=2)
        
        # Find the generated .pyc file
        pycache_dir = src_file.parent / '__pycache__'
        pyc_files = list(pycache_dir.glob(f'{src_file.stem}.*.pyc'))
        
        if pyc_files:
            # Copy .pyc to destination
            dest_file = dest_dir / f'{src_file.stem}.pyc'
            shutil.copy2(pyc_files[0], dest_file)
            return True
    except Exception as e:
        print_error(f"Failed to compile {src_file.name}: {e}")
        return False
    return False

def main():
    print_header("POWER MONITOR - CUSTOMER PACKAGE BUILDER")
    print()
    
    # Directories
    script_dir = Path(__file__).parent
    dist_dir = script_dir / 'customer_package'
    build_dir = script_dir / 'build_temp'
    
    # Clean previous builds
    print_step(1, 7, "Cleaning previous builds...")
    try:
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
    except Exception as e:
        print(f"Warning: Could not remove {dist_dir}: {e}")
    
    try:
        if build_dir.exists():
            shutil.rmtree(build_dir)
    except Exception as e:
        print(f"Warning: Could not remove {build_dir}: {e}")
    
    dist_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    print_success("Clean")
    print()
    
    # Create package structure
    print_step(2, 7, "Creating package structure...")
    pkg_dir = dist_dir / 'power-monitor'
    pkg_src_dir = pkg_dir / 'src'
    pkg_src_dir.mkdir(parents=True)
    print_success("Structure created")
    print()
    
    # Compile Python files
    print_step(3, 7, "Compiling Python source files...")
    src_dir = script_dir / 'src'
    compiled_count: int = 0
    
    for py_file in src_dir.glob('*.py'):
        if py_file.name != '__init__.py':
            if compile_python_file(py_file, pkg_src_dir):
                compiled_count += 1  # type: ignore
                print(f"  [OK] {py_file.name} -> {py_file.stem}.pyc")
    
    # Copy __init__.py as is (needed for package)
    shutil.copy2(src_dir / '__init__.py', pkg_src_dir / '__init__.py')
    
    print_success(f"Compiled {compiled_count} files")
    print()
    
    # Copy necessary files
    print_step(4, 7, "Copying configuration and documentation...")
    files_to_copy = [
        'config.example.json',
        '.env.example',
        'requirements.txt',
        'LICENSE',
        'INSTALL.txt',
        'QUICK_START.txt',
        'GPIO_WIRING.txt'
    ]
    
    for filename in files_to_copy:
        src_file = script_dir / filename
        if src_file.exists():
            shutil.copy2(src_file, pkg_dir / filename)
            print(f"  [OK] {filename}")
        else:
            print_warning(f"  ! {filename} not found, skipping")
    
    print_success("Files copied")
    print()
    
    # Create customer installer
    print_step(5, 7, "Creating customer installer...")
    
    installer_content = '''#!/bin/bash
################################################################################
# Power Monitor - Customer Installation Script
################################################################################

set -e

# Colors
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m'

echo -e "${BLUE}"
cat << "EOF"
+---------------------------------------------------------------╗
|                                                               |
|           POWER MONITOR - INSTALLATION                       |
|                                                               |
|     24/7 EB & Generator Monitoring System                    |
|                                                               |
+---------------------------------------------------------------╝
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
echo -e "${GREEN}[OK]${NC} Installed to: $INSTALL_DIR"

# Step 2: Install system dependencies
echo -e "${BLUE}[2/9]${NC} Installing system dependencies..."
apt-get update
apt-get install -y python3-pip python3-tk mysql-server
echo -e "${GREEN}[OK]${NC} System dependencies installed"

# Step 3: Install Python packages
echo -e "${BLUE}[3/9]${NC} Installing Python packages..."
pip3 install -q --break-system-packages -r "$INSTALL_DIR/requirements.txt"
pip3 install -q --break-system-packages RPi.GPIO python-dotenv
echo -e "${GREEN}[OK]${NC} Python packages installed"

# Step 4: Setup configuration
echo -e "${BLUE}[4/9]${NC} Setting up application configuration..."
if [ ! -f "$INSTALL_DIR/config.json" ]; then
    cp "$INSTALL_DIR/config.example.json" "$INSTALL_DIR/config.json"
    chown $ACTUAL_USER:$ACTUAL_USER "$INSTALL_DIR/config.json"
fi
echo -e "${GREEN}[OK]${NC} Configuration ready"

# Step 5: Run MySQL configuration wizard
echo -e "${BLUE}[5/9]${NC} Configuring MySQL..."
python3 "$INSTALL_DIR/configure_mysql.py"
echo -e "${GREEN}[OK]${NC} MySQL configured"

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
echo -e "${GREEN}[OK]${NC} Service installed and started"

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
echo -e "${GREEN}[OK]${NC} Desktop shortcut created"

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
echo -e "${GREEN}[OK]${NC} Menu entry created"

# Step 9: Set permissions
echo -e "${BLUE}[9/9]${NC} Setting permissions..."
usermod -a -G gpio $ACTUAL_USER > /dev/null 2>&1 || true
chmod -R 755 "$INSTALL_DIR"
echo -e "${GREEN}[OK]${NC} Permissions configured"

echo ""
echo -e "${GREEN}"
cat << "EOF"
+---------------------------------------------------------------╗
|                                                               |
|              INSTALLATION COMPLETED!                          |
|                                                               |
+---------------------------------------------------------------╝
EOF
echo -e "${NC}"

echo -e "${GREEN}Installation Summary:${NC}"
echo ""
echo "  [OK] Background Service (24/7 monitoring)"
echo "  [OK] Desktop GUI Application"
echo "  [OK] Desktop Shortcut"
echo "  [OK] Application Menu Entry"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "  1. Wire GPIO connections (see GPIO_WIRING.txt)"
echo "  2. Configure Email notifications (optional):"
echo "     sudo nano $INSTALL_DIR/.env"
echo "  3. Restart service:"
echo "     sudo systemctl restart power-monitor"
echo "  4. Open GUI: Double-click desktop icon"
echo ""
echo -e "${GREEN}Installation location: $INSTALL_DIR${NC}"
echo ""
'''
    
    installer_file = pkg_dir / 'install.sh'
    installer_file.write_text(installer_content, encoding='utf-8')
    installer_file.chmod(0o755)
    print_success("Installer created")
    print()
    
    # Create MySQL configuration wizard
    print_step(6, 7, "Creating MySQL configuration wizard...")
    
    mysql_config_content = '''#!/usr/bin/env python3
"""MySQL Configuration Wizard for Power Monitor"""
import json
import sys
import getpass
import subprocess

def print_header(text):
    print("=" * 70)
    print(f"{text:^70}")
    print("=" * 70)

def test_mysql_connection(host, port, user, password, database):
    """Test MySQL connection."""
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        conn.close()
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

def main():
    print_header("MySQL Configuration Wizard")
    print()
    print("This wizard will help you configure MySQL for Power Monitor.")
    print()
    
    # Get MySQL credentials
    print("Please enter your MySQL credentials:")
    print()
    
    host = input("MySQL Host [localhost]: ").strip() or "localhost"
    port = input("MySQL Port [3306]: ").strip() or "3306"
    user = input("MySQL User [root]: ").strip() or "root"
    password = getpass.getpass("MySQL Password: ")
    database = input("Database Name [ebpc]: ").strip() or "ebpc"
    
    print()
    print("Testing connection...")
    
    # Test connection
    if test_mysql_connection(host, int(port), user, password, database):
        print("[OK] Connection successful!")
        
        # Update config.json
        config_file = "/opt/power-monitor/config.json"
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            config['database'] = {
                "type": "mysql",
                "host": host,
                "port": int(port),
                "user": user,
                "password": password,
                "database": database
            }
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"[OK] Configuration saved to {config_file}")
            return 0
        except Exception as e:
            print(f"[ERR] Failed to save configuration: {e}")
            return 1
    else:
        print("[ERR] Connection failed. Please check your credentials.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''
    
    mysql_config_file = pkg_dir / 'configure_mysql.py'
    mysql_config_file.write_text(mysql_config_content, encoding='utf-8')
    mysql_config_file.chmod(0o755)
    print_success("MySQL wizard created")
    print()
    
    # Create README
    print_step(7, 7, "Creating customer README...")
    
    readme_content = '''================================================================================
                    POWER MONITOR - INSTALLATION
================================================================================

Thank you for choosing Power Monitor!

QUICK INSTALLATION:
-------------------

1. Extract this package on your Raspberry Pi

2. Open terminal and run:
   
   cd power-monitor
   sudo ./install.sh

3. Follow the on-screen instructions

4. The installer will:
   [OK] Install all dependencies
   [OK] Configure MySQL (interactive wizard)
   [OK] Install 24/7 background service
   [OK] Create desktop shortcut
   [OK] Set up everything automatically

5. Wire GPIO connections (see GPIO_WIRING.txt)

6. Open GUI: Double-click "Power Monitor" icon on desktop

WHAT YOU GET:
-------------

[OK] 24/7 Background Service
  - Monitors GPIO pins continuously
  - Records events to MySQL database
  - Auto-starts on boot
  - Email notifications (optional)

[OK] Desktop GUI Application
  - Real-time status dashboard
  - Timeline graphs
  - Event reports
  - CSV export

GPIO CONNECTIONS:
-----------------

Pin 11 (GPIO 17) ← EB Power Status
Pin 13 (GPIO 27) ← Generator 1 Status
Pin 15 (GPIO 22) ← Generator 2 Status
Pin 6  (GND)     ← Common Ground

[WARN]️ Use 3.3V logic signals!
[WARN]️ Use optocouplers for higher voltages!

EMAIL NOTIFICATIONS (OPTIONAL):
--------------------------------

To enable Email notifications:

1. Prepare an App Password for your email (e.g., Gmail)
2. Compile the template:
   cp /opt/power-monitor/.env.example /opt/power-monitor/.env
   sudo nano /opt/power-monitor/.env

3. Add your credentials:
   EMAIL_ENABLED=true
   EMAIL_RATE_LIMIT_SECONDS=300
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   EMAIL_FROM=your_email@gmail.com
   EMAIL_TO=recipient@example.com

4. Restart service:
   sudo systemctl restart power-monitor

SUPPORT:
--------

For help, see:
- INSTALL.txt (detailed installation guide)
- QUICK_START.txt (quick reference)
- GPIO_WIRING.txt (wiring diagrams)

Installation location: /opt/power-monitor

================================================================================
'''
    
    readme_file = pkg_dir / 'README.txt'
    readme_file.write_text(readme_content, encoding='utf-8')
    print_success("README created")
    print()
    
    # Create archive
    print_header("PACKAGE COMPLETE")
    print()
    print_success(f"Customer package created: {pkg_dir}")
    print()
    print("Package contents:")
    print(f"  * Compiled Python bytecode (.pyc files)")
    print(f"  * Installation script (install.sh)")
    print(f"  * MySQL configuration wizard")
    print(f"  * Configuration templates")
    print(f"  * Customer documentation")
    print()
    print(f"{Colors.GREEN}[OK] NO SOURCE CODE INCLUDED{Colors.NC}")
    print()
    print("To distribute:")
    print(f"  1. Archive: tar -czf power-monitor-installer.tar.gz -C {dist_dir} power-monitor")
    print(f"  2. Send to customer")
    print()

if __name__ == "__main__":
    main()

