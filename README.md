# 🔌 Power Monitor - 24/7 EB & Generator Monitoring System

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-red.svg)](https://www.raspberrypi.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A comprehensive power monitoring system for Raspberry Pi with GPIO integration. Monitors EB (Electricity Board) and multiple generators, records events to MySQL database, and provides a beautiful desktop GUI for 24/7 operation.

---

## 🌟 Features

- 🔌 **GPIO Integration** - Direct hardware monitoring via Raspberry Pi GPIO pins
- ⚡ **Real-time Monitoring** - 0.5s polling with debounce protection  
- 💾 **MySQL Database** - All events recorded with timestamps and durations
- 🖥️ **Desktop GUI** - Beautiful dashboard with LED indicators, graphs, and reports
- 🔄 **24/7 Service** - Runs continuously as systemd/Windows service
- 🔁 **Auto-restart** - Automatically recovers from failures
- 📊 **Power Outage Detection** - Automatic EB power cut detection and tracking
- 📤 **CSV Export** - Export filtered reports for analysis
- 🔒 **Safe** - Optocoupler support for electrical isolation

---

## 🚀 Quick Start

### Installation (3 Steps)

```bash
# 1. Clone repository
git clone https://github.com/YOUR_USERNAME/power-monitor-rpi.git
cd power-monitor-rpi

# 2. Configure database
cp config.example.json config.json
nano config.json  # Add your MySQL password

# 3. Install as service (one command!)
sudo ./install_service_linux.sh
```

**That's it!** The service is now running 24/7 and monitoring your power status.

---

## 🔌 GPIO Wiring

Connect your power status signals to these Raspberry Pi pins:

```
Pin 11 (GPIO 17) ← EB Power Status
Pin 13 (GPIO 27) ← Generator 1 Status
Pin 15 (GPIO 22) ← Generator 2 Status
Pin 6  (GND)     ← Common Ground
```

**Signal Logic:**
- HIGH (3.3V) = Power ON (1)
- LOW (0V) = Power OFF (0)

⚠️ **IMPORTANT:** Never connect voltages > 3.3V directly to GPIO pins!  
Use optocouplers for 5V, 12V, 24V, or AC signals. See [GPIO_WIRING.txt](GPIO_WIRING.txt) for detailed diagrams.

---

## 📖 Documentation

- 📄 [START_HERE.txt](START_HERE.txt) - Begin here!
- 🚀 [QUICK_START.txt](QUICK_START.txt) - Quick reference guide
- 📚 [SETUP_GUIDE.txt](SETUP_GUIDE.txt) - Detailed setup instructions
- 🔌 [GPIO_WIRING.txt](GPIO_WIRING.txt) - Wiring diagrams and safety
- 🏗️ [SYSTEM_ARCHITECTURE.txt](SYSTEM_ARCHITECTURE.txt) - Technical architecture
- ✅ [DEPLOYMENT_CHECKLIST.txt](DEPLOYMENT_CHECKLIST.txt) - Installation checklist
- 📝 [IMPLEMENTATION_SUMMARY.txt](IMPLEMENTATION_SUMMARY.txt) - What was implemented

---

## 🛠️ Requirements

### Hardware
- Raspberry Pi 3/4 or newer
- Power supply (5V, 2.5A minimum)
- MicroSD card (16GB+, Class 10)
- Optocouplers (PC817 or similar) for voltage isolation
- Wiring and connectors

### Software
- Python 3.8 or higher
- MySQL Server 5.7 or higher
- RPi.GPIO library
- Raspberry Pi OS (or any Linux distribution)

---

## 💻 Usage

### Service Management

```bash
# Check status
sudo systemctl status power-monitor

# View live logs
sudo journalctl -u power-monitor -f

# Start/Stop/Restart
sudo systemctl start power-monitor
sudo systemctl stop power-monitor
sudo systemctl restart power-monitor
```

### Desktop GUI

```bash
# Open GUI dashboard
python3 -m src.main
```

Shows:
- Real-time status with LED indicators
- Timeline graphs for all power sources
- Event reports with filtering
- EB power cut history
- CSV export functionality

### Testing

```bash
# Test GPIO reading
python3 -m src.gpio_reader

# Test service manually
python3 run_monitor_service.py
```

---

## 📊 What It Does

The system continuously:
- ✅ Monitors GPIO pins every 0.5 seconds
- ✅ Detects state changes (ON/OFF)
- ✅ Records all events to MySQL database
- ✅ Calculates durations and intervals
- ✅ Detects power outages automatically
- ✅ Logs all activities
- ✅ Auto-starts on boot
- ✅ Auto-restarts on failure

**Performance:**
- CPU usage: < 1%
- Memory: 50-100 MB
- Reliable 24/7 operation

---

## 🎯 Key Benefits

✅ **No Manual Intervention** - Runs 24/7 automatically  
✅ **Reliable** - Auto-restarts on failure  
✅ **Complete History** - All events recorded with timestamps  
✅ **Easy Installation** - One command to install  
✅ **Safe** - Optocoupler support for electrical isolation  
✅ **Comprehensive Docs** - Everything is documented  
✅ **Cross-Platform** - Works on Raspberry Pi, Linux, Windows  

---

## 🏗️ Project Structure

```
power-monitor-rpi/
├── src/                         # Source code
│   ├── gpio_reader.py          # GPIO pin reading
│   ├── background_monitor.py   # 24/7 monitoring service
│   ├── monitor_gui.py          # Desktop GUI
│   ├── db_reader.py            # Database read operations
│   ├── db_writer.py            # Database write operations
│   └── config.py               # Configuration loader
│
├── Installation Scripts
│   ├── install_service_linux.sh       # Linux/RPi installer
│   ├── install_service_windows.bat    # Windows installer
│   ├── install_windows_service.py     # Windows service
│   ├── power-monitor.service          # systemd service file
│   └── run_monitor_service.py         # Manual runner
│
├── Documentation
│   ├── START_HERE.txt
│   ├── QUICK_START.txt
│   ├── SETUP_GUIDE.txt
│   ├── GPIO_WIRING.txt
│   └── ...
│
├── config.example.json          # Sample configuration
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## 🔧 Troubleshooting

### Service won't start
```bash
sudo journalctl -u power-monitor -xe  # Check logs
sudo systemctl status mysql            # Verify MySQL
cat config.json                        # Check config
```

### GPIO not reading
```bash
python3 -m src.gpio_reader  # Test manually
groups pi                   # Check permissions
```

### Database errors
```bash
mysql -u root -p  # Test connection
nano config.json  # Verify credentials
```

See [SETUP_GUIDE.txt](SETUP_GUIDE.txt) for detailed troubleshooting.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Support

For issues and questions:
- Open an issue on GitHub
- Check the documentation files
- Review the troubleshooting section

---

## 📸 Screenshots

*Coming soon - Desktop GUI dashboard, timeline graphs, and reports*

---

**Made with ❤️ for reliable 24/7 power monitoring**

---

# Raspberry Pi Monitor - Desktop Event Viewer

> **Note:** The sections below contain the original GUI documentation.

A cross-platform desktop application built with Python and Tkinter that provides a read-only GUI for viewing events from a Raspberry Pi generator and power-cut monitoring system. The application connects to a MySQL database where events are stored by a background monitoring service.

## Overview

This is a **read-only viewer application**. It does not perform GPIO monitoring itself - it only reads from the MySQL database to display, filter, inspect, and export monitoring events. The actual GPIO monitoring is performed by a separate background systemd service.

## Features

- ✅ **Main Table View**: Sortable columns showing recent events (ID, input name, event type, timestamp, duration, previous interval, metadata)
- ✅ **Pagination**: Handles large datasets efficiently with page-based navigation
- ✅ **Advanced Filtering**: Filter by input (EB/GEN1/GEN2/GEN3), time-range, event type, and free-text search
- ✅ **Event Details**: Double-click or view details button to see full metadata and computed fields
- ✅ **CSV Export**: Export selected rows or filtered results to CSV
- ✅ **Auto-refresh**: Configurable auto-refresh interval (default 30 seconds) with manual refresh option
- ✅ **Visual Indicators**: Red banner showing active power outages (when EB is LOW)
- ✅ **Statistics Panel**: Summary stats including event counts per input, total outages, average duration
- ✅ **Error Handling**: Clear user messages when database is inaccessible or corrupt
- ✅ **Configuration**: Config file support for DB path, auto-refresh interval, default filters, UTC/local time
- ✅ **Keyboard Shortcuts**: F5 (refresh), Ctrl+F (search), Ctrl+E (export), Esc (clear filters)
- ✅ **Minimal Dependencies**: Only requires MySQL connector (Tkinter is part of Python stdlib)

## Requirements

- Python 3.7 or higher
- Tkinter (usually included with Python)
- MySQL connector: `mysql-connector-python` or `pymysql`
- Access to MySQL database with monitoring events

### Installing Dependencies

```bash
pip install mysql-connector-python
# OR
pip install pymysql
```

## Database Connection

The application connects to a MySQL database to read events. Configure the connection in `config.json`:

```json
{
  "database": {
    "type": "mysql",
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "your_password",
    "database": "rpi_monitor"
  }
}
```

## Database Schema

The application expects the following MySQL database schema:

### Events Table
```sql
CREATE TABLE IF NOT EXISTS events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    input_id VARCHAR(50) NOT NULL,
    input_name VARCHAR(100) NOT NULL,
    state INT NOT NULL,
    timestamp DOUBLE NOT NULL,
    event_counter INT NOT NULL,
    previous_off_time DOUBLE,
    previous_on_time DOUBLE,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_input_timestamp (input_id, timestamp),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Intervals Table
```sql
CREATE TABLE IF NOT EXISTS intervals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    input_id VARCHAR(50) NOT NULL,
    on_duration DOUBLE,
    off_interval DOUBLE,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Outages Table
```sql
CREATE TABLE IF NOT EXISTS outages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    outage_start DOUBLE NOT NULL,
    outage_end DOUBLE,
    generator_input_id VARCHAR(50),
    generator_start_time DOUBLE,
    duration_seconds DOUBLE,
    notification_sent INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_outage_start (outage_start)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## Configuration

Edit `config.json` to configure the application:

```json
{
  "database": {
    "type": "mysql",
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "12345678",
    "database": "rpi_monitor"
  },
  "ui": {
    "auto_refresh_interval": 30,
    "default_page_size": 100,
    "show_utc": false,
    "window_width": 1200,
    "window_height": 800
  },
  "default_filters": {
    "input_id": null,
    "start_time": null,
    "end_time": null,
    "event_type": null
  }
}
```

### Configuration Options

- **database**: MySQL connection settings
  - `host`: MySQL server hostname
  - `port`: MySQL server port (default: 3306)
  - `user`: MySQL username
  - `password`: MySQL password
  - `database`: Database name

- **ui**: User interface settings
  - `auto_refresh_interval`: Seconds between auto-refresh (default: 30)
  - `default_page_size`: Number of events per page (default: 100)
  - `show_utc`: Display timestamps in UTC (default: false)
  - `window_width`: Initial window width (default: 1200)
  - `window_height`: Initial window height (default: 800)

## Running the Application

### Method 1: Direct Python Execution

```bash
python3 monitor_ui.py
```

### Method 2: Using Python Module

```bash
python3 -m src.main
```

### Method 3: Using Custom Config

```bash
python3 monitor_ui.py --config /path/to/config.json
```

## Usage Guide

### Viewing Events

1. The main table shows recent events with pagination controls at the bottom
2. Click column headers to sort by that column
3. Use pagination buttons (First, Prev, Next, Last) to navigate through pages

### Filtering Events

1. **Input Filter**: Select specific input (EB, GEN1, GEN2, GEN3) or "All"
2. **Event Type**: Filter by "ON", "OFF", or "All"
3. **Time Range**: Enter start and/or end times (format: YYYY-MM-DD HH:MM:SS)
4. **Search**: Free-text search in input names and metadata
5. Click "Apply Filters" to apply, or "Clear" to reset all filters

### Viewing Event Details

- Double-click any event row, or
- Select an event and click "View Details" button

The details window shows:
- All event fields
- Formatted durations
- Previous event times
- Full metadata JSON

### Exporting to CSV

1. Optionally select specific events (or leave unselected for all filtered events)
2. Click "Export CSV" button
3. Choose save location
4. CSV file will contain all event data with timestamps

### Auto-Refresh

- Check "Auto-refresh" checkbox to enable
- Set interval in seconds (5-300)
- Auto-refresh updates the table and statistics every N seconds
- Press F5 for manual refresh anytime

### Keyboard Shortcuts

- **F5**: Refresh data
- **Ctrl+F**: Focus search field
- **Ctrl+E**: Export CSV
- **Esc**: Clear all filters

## Packaging with PyInstaller

### Installing PyInstaller

```bash
pip install pyinstaller
```

### Building Executable

#### For Raspberry Pi OS (ARM):

```bash
# On Raspberry Pi or cross-compile environment
pyinstaller monitor_ui.spec

# The executable will be in dist/rpi-monitor-ui
```

#### For Desktop Development (Linux/macOS/Windows):

```bash
# Build for current platform
pyinstaller monitor_ui.spec

# The executable will be in dist/rpi-monitor-ui (or rpi-monitor-ui.exe on Windows)
```

### PyInstaller Spec File

The `monitor_ui.spec` file is already configured. Key settings:

- `console=False`: Run as GUI application (set to `True` for debugging)
- `upx=True`: Compress executable (optional)
- `datas=[('config.json', '.')]`: Include config file if needed

### Custom Build Options

Edit `monitor_ui.spec` to:
- Add icon: `icon='path/to/icon.ico'`
- Include additional data files
- Change executable name
- Adjust UPX compression settings

## Architecture

### Components

1. **src/db_reader.py**: Read-only MySQL database access layer
2. **src/config.py**: Configuration management
3. **src/monitor_gui.py**: Main Tkinter GUI application
4. **src/main.py**: Application entry point

### Database Reader

The `DatabaseReader` class provides:
- Connection management
- Event querying with filters and pagination
- Statistics calculation
- Latest state retrieval
- Active outage detection

### GUI Application

The `MonitorGUI` class manages:
- UI layout and components
- User interactions
- Data loading and display
- Filtering and sorting
- Export functionality
- Auto-refresh scheduling

## Error Handling

The application handles various error conditions:

- **Database Connection Errors**: Shows error dialog and exits if connection fails on startup
- **Query Errors**: Shows error message but keeps application running
- **Invalid Filters**: Gracefully handles invalid date/time formats
- **Export Errors**: Shows error message if CSV export fails
- **Connection Status**: Status indicator shows connection state (green=connected, red=error)

## Performance Considerations

- **Pagination**: Large datasets are loaded in pages (default 100 events per page)
- **Lazy Loading**: Only loads current page, not all events
- **Indexed Queries**: Database queries use indexed columns for fast retrieval
- **Efficient Updates**: Statistics and outage checks are optimized

## Troubleshooting

### Database Connection Issues

1. Check MySQL is running: `sudo systemctl status mysql`
2. Verify credentials in `config.json`
3. Test connection: `mysql -h localhost -u root -p`
4. Check firewall allows MySQL connections

### Tkinter Not Available

- **macOS**: `brew install python-tk`
- **Ubuntu/Debian**: `sudo apt-get install python3-tk`
- **Raspberry Pi OS**: Usually pre-installed

### Application Won't Start

1. Check Python version: `python3 --version` (needs 3.7+)
2. Verify dependencies: `pip list | grep mysql`
3. Check config file syntax: `python3 -m json.tool config.json`
4. Check logs for error messages

### No Events Displayed

1. Verify database has events: `SELECT COUNT(*) FROM events;`
2. Check filters aren't too restrictive
3. Verify database schema matches expected format
4. Check database permissions for read access

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
1. Check this README
2. Review error messages in application
3. Check database connectivity and schema
4. Verify configuration file format



