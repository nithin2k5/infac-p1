# 🔌 Power Monitor - Complete Solution

**24/7 EB & Generator Monitoring System for Raspberry Pi**

A professional power monitoring system with GPIO integration, Email notifications, and desktop GUI - ready for customer deployment without exposing source code.

---

## 🌟 Features

### ✅ **24/7 Background Monitoring**
- Continuous GPIO pin monitoring (0.5s polling)
- Automatic event recording to MySQL database
- Power outage detection and tracking
- Auto-starts on boot, auto-restarts on failure

### ✅ **Email Notifications**
- Power outage alerts
- Generator activation notifications **with interval time**
- Power restoration alerts
- Configurable cooldown period

### ✅ **Desktop GUI Application**
- Real-time status dashboard with LED indicators
- Timeline graphs for all power sources
- Event reports with filtering and search
- EB power cut history
- CSV export functionality

### ✅ **Customer-Ready Deployment**
- Compiled bytecode (no source code exposure)
- One-command installation
- Interactive MySQL configuration wizard
- Professional packaging

---

## 📋 Table of Contents

1. [For Developers](#for-developers-build--deploy)
2. [For Customers](#for-customers-installation)
3. [Email Notifications](#email-notifications)
4. [MySQL Configuration](#mysql-configuration)
5. [GPIO Wiring](#gpio-wiring)
6. [UI Features](#ui-features)
7. [Troubleshooting](#troubleshooting)

---

## 👨‍💻 For Developers: Build & Deploy

### **Step 1: Build Customer Package**

```bash
cd /Users/nithinkumark/Developer/python/infac-p1
python3 build_customer_package.py
```

**Output:**
```
╔═══════════════════════════════════════════════════════════════╗
║     POWER MONITOR - CUSTOMER PACKAGE BUILDER                 ║
╚═══════════════════════════════════════════════════════════════╝

[1/7] Cleaning previous builds...
✓ Clean

[2/7] Creating package structure...
✓ Structure created

[3/7] Compiling Python source files...
  ✓ background_monitor.py → background_monitor.pyc
  ✓ config.py → config.pyc
  ✓ db_reader.py → db_reader.pyc
  ✓ db_writer.py → db_writer.pyc
  ✓ gpio_reader.py → gpio_reader.pyc
  ✓ main.py → main.pyc
  ✓ monitor_gui.py → monitor_gui.pyc
  ✓ email_sender.py → email_sender.pyc
✓ Compiled 8 files

[4/7] Copying configuration and documentation...
✓ Files copied

[5/7] Creating customer installer...
✓ Installer created

[6/7] Creating MySQL configuration wizard...
✓ MySQL wizard created

[7/7] Creating customer README...
✓ README created

╔═══════════════════════════════════════════════════════════════╗
║              PACKAGE COMPLETE                                 ║
╚═══════════════════════════════════════════════════════════════╝

✓ Customer package created: customer_package/power-monitor/
✓ NO SOURCE CODE INCLUDED
```

### **Step 2: Create Distribution Archive**

```bash
cd customer_package
tar -czf power-monitor-installer.tar.gz power-monitor/
```

### **Step 3: Send to Customer**

Send the file: `power-monitor-installer.tar.gz`

**What's Included:**
- ✅ Compiled `.pyc` files (bytecode)
- ✅ Automatic installer
- ✅ MySQL configuration wizard
- ✅ Customer documentation
- ✅ Configuration templates
- ❌ **NO** `.py` source files
- ❌ **NO** development files

---

## 👥 For Customers: Installation

### **Step 1: Extract Package**

```bash
tar -xzf power-monitor-installer.tar.gz
cd power-monitor
```

### **Step 2: Run Installer**

```bash
sudo ./install.sh
```

**The installer will:**
1. Install system dependencies (Python, MySQL, Tkinter)
2. Install Python packages
3. Run MySQL configuration wizard (interactive)
4. Install 24/7 background service
5. Create desktop shortcut
6. Create application menu entry
7. Set up permissions

### **Step 3: MySQL Configuration (Automatic)**

During installation, you'll see:

```
[4/9] Configuring MySQL...

╔═══════════════════════════════════════════════════════════════╗
║              MySQL Configuration Wizard                       ║
╚═══════════════════════════════════════════════════════════════╝

This wizard will help you configure MySQL for Power Monitor.

Please enter your MySQL credentials:

MySQL Host [localhost]: ← Press Enter
MySQL Port [3306]: ← Press Enter
MySQL User [root]: ← Press Enter
MySQL Password: ******** ← Enter your password
Database Name [ebpc]: ← Press Enter

Testing connection...
✓ Connection successful!
✓ Configuration saved to /opt/power-monitor/config.json
```

**You only need to enter your MySQL password!** Everything else uses smart defaults.

### **Step 4: Wire GPIO Connections**

```
Pin 11 (GPIO 17) ← EB Power Status
Pin 13 (GPIO 27) ← Generator 1 Status
Pin 15 (GPIO 22) ← Generator 2 Status
Pin 6  (GND)     ← Common Ground
```

⚠️ **IMPORTANT:** Use 3.3V logic signals. For higher voltages, use optocouplers!

See `GPIO_WIRING.txt` for detailed diagrams.

### **Step 5: Use the Application**

**Open GUI:**
- Double-click "Power Monitor" icon on desktop
- OR: Menu → Accessories → Power Monitor

**Service runs automatically 24/7 in background!**

---

## 📧 Email Notifications

### **Setup (Optional)**

1. Prepare an App Password for your email (e.g., Gmail)

2. Create your `.env` file from the provided example:
```bash
cp /opt/power-monitor/.env.example /opt/power-monitor/.env
sudo nano /opt/power-monitor/.env
```

3. Add configuration:
```bash
EMAIL_ENABLED=true
EMAIL_RATE_LIMIT_SECONDS=300
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=recipient@example.com
```

4. Restart service:
```bash
sudo systemctl restart power-monitor
```

### **Notification Examples**

**Power Outage:**
```
⚠️ POWER OUTAGE DETECTED

EB Power: OFF
Time: 2026-01-04 16:30:00

Generator Status:
• GEN1: OFF ❌
• GEN2: OFF ❌

System switched to generator power.
```

**Generator Activation (WITH INTERVAL TIME):**
```
🚨 Power Event Alert

⚡ Generator Activated: Generator 1 (GEN1)

📅 Power Cut Started:
   2026-01-04 16:30:00

🔄 Generator Started:
   2026-01-04 16:32:15

⏱️ INTERVAL TIME (Power Cut → Generator ON):
   2 minutes 15 seconds
   (135 seconds)

Status: Generator is now active
```

**Power Restored:**
```
✅ POWER RESTORED

EB Power: ON
Restored at: 2026-01-04 16:45:30

Outage Duration: 15 minutes 30 seconds
Outage started: 16:30:00

System back to normal power.
```

---

## 🗄️ MySQL Configuration

### **Initial Configuration**
Done automatically during installation via interactive wizard.

### **Reconfigure MySQL**
If you need to change MySQL settings:

```bash
sudo python3 /opt/power-monitor/configure_mysql.py
```

### **Manual Configuration**
Edit configuration file:

```bash
sudo nano /opt/power-monitor/config.json
```

Update the database section:
```json
{
  "database": {
    "type": "mysql",
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "your_password",
    "database": "ebpc"
  }
}
```

Restart service:
```bash
sudo systemctl restart power-monitor
```

---

## 🔌 GPIO Wiring

### **Pin Assignments**

| Function | GPIO Pin | Physical Pin | Signal |
|----------|----------|--------------|--------|
| EB Status | GPIO 17 | Pin 11 | 3.3V Logic |
| GEN1 Status | GPIO 27 | Pin 13 | 3.3V Logic |
| GEN2 Status | GPIO 22 | Pin 15 | 3.3V Logic |
| Ground | GND | Pin 6 | Common Ground |

### **Signal Logic**
- **HIGH (3.3V)** = Power ON (1)
- **LOW (0V)** = Power OFF (0)

### **Safety Warning**
⚠️ **NEVER** connect voltages > 3.3V directly to GPIO pins!

For 5V, 12V, 24V, or AC signals, use optocouplers (e.g., PC817) for electrical isolation.

See `GPIO_WIRING.txt` for detailed wiring diagrams and safety information.

---

## 🖥️ UI Features

### **✅ YES! Desktop GUI is Available**

The system includes a **full-featured desktop GUI application** with:

### **1. Status Dashboard Tab**
- **Real-time LED Indicators**
  - EB (Electricity Board) - Shows ON/OFF with red LED
  - GEN1 (Generator 1) - Shows ON/OFF with red LED
  - GEN2 (Generator 2) - Shows ON/OFF with red LED
- **Timeline Graph**
  - Visual representation of all power sources
  - Last 4 hours of activity
  - Color-coded for each source
- **Auto-refresh** (configurable, default 30 seconds)
- **Last updated timestamp**

### **2. Events Report Tab**
- **Complete Event Log**
  - All state changes recorded
  - Timestamps with durations
  - ON/OFF intervals
- **Advanced Filtering**
  - Filter by input (EB/GEN1/GEN2)
  - Filter by event type (ON/OFF)
  - Date/time range filtering
  - Text search
- **Sortable Columns**
- **Pagination** (handles large datasets)
- **View Event Details** (double-click)
- **CSV Export** (filtered or all data)
- **Statistics Panel**
  - Total events
  - Events per input
  - ON/OFF counts

### **3. EB Power History Tab**
- **Power Cut Tracking**
  - OFF time → ON time
  - Duration of each outage
  - Status (Ongoing/Completed)
- **Pagination**
- **Color-coded** (red for ongoing, green for completed)

### **Opening the GUI**

**Method 1:** Double-click desktop icon
```
Desktop → Power Monitor icon
```

**Method 2:** Application menu
```
Menu → Accessories → Power Monitor
```

**Method 3:** Command line
```bash
python3 /opt/power-monitor/src/main.pyc
```

### **GUI Screenshots Description**

**Status Dashboard:**
- Top section: 4 LED indicators in a row (EB, GEN1, GEN2, GEN3)
- Each shows: Name, LED circle (red=ON, gray=OFF), status text, last update time
- Bottom section: Combined timeline graph showing all inputs over last 4 hours
- Refresh button and auto-refresh checkbox

**Events Report:**
- Statistics panel at top (total events, counts per input)
- Filter panel (input selector, event type, date range, search box)
- Main table with columns: ID, Input, State, Timestamp, Counter, Durations
- Pagination controls at bottom
- Export CSV and View Details buttons

**EB Power History:**
- Table showing: #, OFF Time, ON Time, Duration, Status
- Color-coded rows (red=ongoing, green=completed)
- Pagination controls
- Refresh button

---

## 🔧 Service Management

### **Check Status**
```bash
sudo systemctl status power-monitor
```

### **View Live Logs**
```bash
sudo journalctl -u power-monitor -f
```

### **Restart Service**
```bash
sudo systemctl restart power-monitor
```

### **Stop/Start Service**
```bash
sudo systemctl stop power-monitor
sudo systemctl start power-monitor
```

---

## 🐛 Troubleshooting

### **Service Won't Start**
```bash
# Check detailed logs
sudo journalctl -u power-monitor -xe

# Verify MySQL is running
sudo systemctl status mysql

# Check configuration
cat /opt/power-monitor/config.json
```

### **GPIO Not Reading**
```bash
# Test GPIO manually
python3 -m src.gpio_reader

# Check user permissions
groups pi

# Verify wiring connections
```

### **MySQL Connection Failed**
```bash
# Reconfigure MySQL
sudo python3 /opt/power-monitor/configure_mysql.py

# Test MySQL connection
mysql -u root -p
```

### **Email Not Working**
```bash
# Check .env file exists
ls -la /opt/power-monitor/.env

# Verify configuration
cat /opt/power-monitor/.env

# Check service logs
sudo journalctl -u power-monitor | grep -i email
```

### **GUI Won't Open**
```bash
# Check Tkinter is installed
python3 -m tkinter

# Run from terminal to see errors
python3 /opt/power-monitor/src/main.pyc

# Verify database connection
python3 -c "from src.db_reader import DatabaseReader; db = DatabaseReader(); print('OK' if db.test_connection() else 'FAIL')"
```

---

## 📊 System Requirements

### **Hardware**
- Raspberry Pi 3/4 or newer
- Power supply (5V, 2.5A minimum)
- MicroSD card (16GB+, Class 10)
- Optocouplers (for voltage isolation)

### **Software**
- Raspberry Pi OS (Debian-based)
- Python 3.8 or higher
- MySQL Server 5.7 or higher
- Tkinter (GUI support)

### **Performance**
- CPU usage: < 1%
- Memory: 50-100 MB (service), 100-200 MB (GUI when open)
- Disk space: ~1 GB (including database)

---

## 📚 Documentation

- **raspberry_pi_setup.txt** - Complete Raspberry Pi installation and wiring guide
- **raspberry_pi_services.txt** - Background service operations and commands
- **raspberry_pi_pin_configuration.txt** - GPIO pin assignments and logic

---

## 🔒 Security

### **Source Code Protection**
- All Python files compiled to bytecode (`.pyc`)
- Original `.py` source files NOT included
- Difficult to reverse engineer
- Your intellectual property is protected

### **What Customers Get**
- ✅ Working application (all features)
- ✅ Easy installation
- ✅ Professional package
- ❌ **NO** source code access
- ❌ **NO** ability to modify core logic

---

## 📦 Project Structure

```
infac-p1/
├── src/                              # Source code
│   ├── background_monitor.py         # 24/7 monitoring service
│   ├── config.py                     # Configuration loader
│   ├── db_reader.py                  # Database reading
│   ├── db_writer.py                  # Database writing
│   ├── gpio_reader.py                # GPIO pin reading
│   ├── main.py                       # GUI entry point
│   ├── monitor_gui.py                # GUI application
│   └── email_sender.py               # Email notifications
│
├── build_customer_package.py         # Build customer package
├── config.example.json               # Configuration template
├── .env.example                      # WhatsApp credentials template
├── requirements.txt                  # Python dependencies
├── LICENSE                           # MIT License
│
└── Documentation/
    ├── README.md                          # This file
    ├── raspberry_pi_setup.txt             # Raspberry Pi installation guide
    ├── raspberry_pi_services.txt          # Background service details
    └── raspberry_pi_pin_configuration.txt # GPIO pin assignments
```

---

## 🎯 Quick Start Summary

### **For Developers:**
```bash
python3 build_customer_package.py
cd customer_package
tar -czf power-monitor-installer.tar.gz power-monitor/
# Send to customer
```

### **For Customers:**
```bash
tar -xzf power-monitor-installer.tar.gz
cd power-monitor
sudo ./install.sh
# Enter MySQL password when prompted
# Wire GPIO connections
# Double-click desktop icon
```

---

## 📄 License

MIT License - See LICENSE file for details.

---

## 🙏 Support

For issues, questions, or support:
- Check documentation files
- Review troubleshooting section
- Contact: [Your contact information]

---

**Made with ❤️ for reliable 24/7 power monitoring**

---

## ✅ Checklist

- [x] 24/7 background monitoring service
- [x] Desktop GUI application with LED indicators and graphs
- [x] Email notifications with interval time
- [x] Easy MySQL configuration wizard
- [x] Compiled package (no source code)
- [x] One-command installation
- [x] GPIO pin monitoring
- [x] Auto-start on boot
- [x] Professional documentation
- [x] Customer-ready deployment

**Everything is ready for deployment!** 🚀
