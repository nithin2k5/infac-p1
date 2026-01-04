================================================================================
                    POWER MONITOR - INSTALLATION
================================================================================

Thank you for choosing Power Monitor!

QUICK INSTALLATION:
-------------------

1. Copy this folder to your Raspberry Pi

2. Open terminal and run:
   
   cd power-monitor
   sudo ./install.sh

3. Follow the on-screen instructions

4. Configure database password:
   sudo nano /opt/power-monitor/config.json

5. Wire GPIO connections (see GPIO_WIRING.txt)

6. Restart service:
   sudo systemctl restart power-monitor

7. Open GUI: Double-click "Power Monitor" icon on desktop

WHAT YOU GET:
-------------

✓ 24/7 Background Service
  - Monitors GPIO pins continuously
  - Records events to MySQL database
  - Auto-starts on boot

✓ Desktop GUI Application
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

⚠️ Use 3.3V logic signals!
⚠️ Use optocouplers for higher voltages!

SUPPORT:
--------

For help, see:
- INSTALL.txt (detailed installation guide)
- QUICK_START.txt (quick reference)
- GPIO_WIRING.txt (wiring diagrams)

================================================================================
