# Power Monitor - 24/7 EB & Generator Monitoring System

A comprehensive power monitoring system designed for 24/7 operation on Raspberry Pi with GPIO integration. Monitors EB (Electricity Board) and multiple generators, records events to MySQL database, and provides a beautiful desktop GUI for viewing reports and analytics.

## 🌟 Features

### 🔌 Hardware Integration
- **Raspberry Pi GPIO Support**: Direct reading from GPIO pins
- **Pin Assignments**:
  - GPIO 17 (Pin 11) → EB Power Status
  - GPIO 27 (Pin 13) → Generator 1 Status
  - GPIO 22 (Pin 15) → Generator 2 Status
- **Real-time Monitoring**: 0.5-second polling with debounce protection
- **Optocoupler Support**: Safe isolation for high-voltage signals

### 💾 Database & Storage
- MySQL database for event storage
- Automatic table creation and management
- Event tracking with timestamps and durations
- Power outage history with duration calculations
- Efficient indexing for fast queries

### 🖥️ Desktop GUI Application
- **Status Dashboard**: Real-time LED indicators for all power sources
- **Timeline Graph**: Visual representation of power status over time
- **Events Report**: Detailed event log with filtering and search
- **EB Power History**: Track power cuts with duration analysis
- **Export to CSV**: Export filtered data for analysis
- **Auto-refresh**: Configurable automatic data refresh

### 🔄 24/7 Background Service
- **Windows Service**: Runs as Windows service with auto-start
- **Linux systemd Service**: Runs as systemd service on Linux/Raspberry Pi
- **Auto-restart**: Automatically restarts on failure
- **Logging**: Comprehensive logging to file and system journal
- **Low Resource Usage**: Minimal CPU and memory footprint

### 📊 Monitoring & Analytics
- Real-time power status monitoring
- Event counting and statistics
- Duration calculations (ON time, OFF intervals)
- Power outage detection and tracking
- Historical data analysis

## 🚀 Quick Start

### Raspberry Pi (3 Steps)

```bash
# 1. Install as service
sudo ./install_service_linux.sh

# 2. Check status
sudo systemctl status power-monitor

# 3. View live logs
sudo journalctl -u power-monitor -f
```

### Windows (2 Steps)

```batch
REM 1. Run as Administrator
install_service_windows.bat

REM 2. Check status
sc query PowerMonitorService
```

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- MySQL Server 5.7 or higher
- Raspberry Pi (for GPIO monitoring) or any Linux/Windows machine

### Raspberry Pi Setup

1. **Clone/Copy the project**:
   ```bash
   git clone <repository-url>
   cd infac-p1
   ```

2. **Install system dependencies**:
   ```bash
   sudo apt-get update
   sudo apt-get install python3-pip python3-tk mysql-server
   ```

3. **Install Python dependencies**:
   ```bash
   pip3 install -r requirements.txt
   pip3 install RPi.GPIO
   ```

4. **Configure database**:
   Edit `config.json` with your MySQL credentials:
   ```json
   {
     "database": {
       "host": "localhost",
       "user": "root",
       "password": "your_password",
       "database": "ebpc"
     }
   }
   ```

5. **Test GPIO reading** (optional):
   ```bash
   python3 -m src.gpio_reader
   ```

6. **Install as service**:
   ```bash
   sudo ./install_service_linux.sh
   ```

### Windows Setup

1. **Install Python dependencies**:
   ```batch
   pip install -r requirements.txt
   pip install pywin32
   ```

2. **Configure database** in `config.json`

3. **Install as Windows Service**:
   ```batch
   REM Run as Administrator
   install_service_windows.bat
   ```

## 🔌 GPIO Wiring

### Pin Connections

Connect your power status signals to these Raspberry Pi GPIO pins:

```
Pin 11 (GPIO 17) ← EB Power Status
Pin 13 (GPIO 27) ← Generator 1 Status
Pin 15 (GPIO 22) ← Generator 2 Status
Pin 6  (GND)     ← Common Ground
```

### Signal Logic

- **HIGH (3.3V)** = Power ON (1)
- **LOW (0V/GND)** = Power OFF (0)

### ⚠️ Safety Warning

**NEVER connect voltages higher than 3.3V directly to GPIO pins!**

For 5V, 12V, 24V, or AC signals, use optocouplers (e.g., PC817) for electrical isolation.

See `GPIO_WIRING.txt` for detailed wiring diagrams and safety instructions.

## 💻 Usage

### Running the GUI

```bash
# Desktop application with dashboard
python3 -m src.main
```

### Running as Background Service

**Linux/Raspberry Pi**:
```bash
# Start service
sudo systemctl start power-monitor

# Stop service
sudo systemctl stop power-monitor

# View logs
sudo journalctl -u power-monitor -f

# Check status
sudo systemctl status power-monitor
```

**Windows**:
```batch
REM Start service
python install_windows_service.py start

REM Stop service
python install_windows_service.py stop

REM Check logs
type service.log
```

### Testing GPIO

```bash
# Test GPIO pin reading
python3 -m src.gpio_reader
```

This will show real-time status of all GPIO pins. Toggle your power sources to verify correct reading.

## ⚙️ Configuration

Edit `config.json` to customize:

```json
{
  "database": {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "your_password",
    "database": "ebpc"
  },
  "gpio": {
    "enabled": true,
    "poll_interval": 0.5,
    "debounce_time": 0.1,
    "pins": {
      "eb": 17,
      "gen1": 27,
      "gen2": 22
    }
  },
  "ui": {
    "auto_refresh_interval": 30,
    "default_page_size": 100,
    "window_width": 1200,
    "window_height": 800
  }
}
```

## 🏗️ Building Windows Executable

To create standalone `.exe` files:

```bash
# Install PyInstaller
pip install pyinstaller

# Run build script
python build_exe.py
```

Executables will be created in the `dist` folder:
- `PowerMonitorGUI.exe` - Desktop application
- `PowerMonitorService.exe` - Background service

## 📁 Project Structure

```
infac-p1/
├── src/
│   ├── __init__.py
│   ├── main.py              # GUI entry point
│   ├── monitor_gui.py       # GUI application
│   ├── config.py            # Configuration loader
│   ├── db_reader.py         # Database read operations
│   ├── db_writer.py         # Database write operations
│   ├── gpio_reader.py       # GPIO pin reading
│   ├── background_monitor.py # 24/7 monitoring service
│   └── whatsapp_sender.py   # WhatsApp notifications
├── config.json              # Configuration file
├── requirements.txt         # Python dependencies
├── install_service_linux.sh # Linux service installer
├── install_service_windows.bat # Windows service installer
├── install_windows_service.py # Windows service implementation
├── power-monitor.service    # systemd service file
├── run_monitor_service.py   # Service runner script
├── build_exe.py            # Executable builder
├── SETUP_GUIDE.txt         # Detailed setup guide
├── QUICK_START.txt         # Quick start guide
├── GPIO_WIRING.txt         # Wiring diagrams
└── README.md               # Original README
```

## 🔧 Troubleshooting

### Service won't start

```bash
# Check logs
sudo journalctl -u power-monitor -xe

# Verify MySQL is running
sudo systemctl status mysql

# Check configuration
cat config.json
```

### GPIO not reading

```bash
# Test GPIO
python3 -m src.gpio_reader

# Check permissions
sudo usermod -a -G gpio $USER

# Verify wiring connections
```

### Database connection failed

```bash
# Test MySQL connection
mysql -u root -p

# Check MySQL status
sudo systemctl status mysql

# Verify credentials in config.json
```

## 📊 Performance

- **CPU Usage**: < 1%
- **Memory Usage**: 50-100 MB
- **GPIO Polling**: 0.5 seconds (configurable)
- **Database Size**: ~1 MB per 10,000 events

## 🛠️ Maintenance

### Database Backup

```bash
# Backup database
mysqldump -u root -p ebpc > backup_$(date +%Y%m%d).sql

# Restore database
mysql -u root -p ebpc < backup_20260104.sql
```

### Log Management

```bash
# View recent logs (Linux)
sudo journalctl -u power-monitor -n 100

# Clear old logs
sudo journalctl --vacuum-time=7d
```

## 📚 Documentation

- **SETUP_GUIDE.txt** - Comprehensive setup instructions
- **QUICK_START.txt** - Quick reference guide
- **GPIO_WIRING.txt** - Detailed wiring diagrams and safety information
- **README.md** - Original GUI application documentation

## 📄 License

[Your License Here]

## 💬 Support

For issues, questions, or contributions, please [contact information or repository issues page].

---

**Made with ❤️ for reliable 24/7 power monitoring**

