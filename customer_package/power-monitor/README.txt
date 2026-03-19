================================================================================
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
