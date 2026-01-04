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
   ✓ Install all dependencies
   ✓ Configure MySQL (interactive wizard)
   ✓ Install 24/7 background service
   ✓ Create desktop shortcut
   ✓ Set up everything automatically

5. Wire GPIO connections (see GPIO_WIRING.txt)

6. Open GUI: Double-click "Power Monitor" icon on desktop

WHAT YOU GET:
-------------

✓ 24/7 Background Service
  - Monitors GPIO pins continuously
  - Records events to MySQL database
  - Auto-starts on boot
  - WhatsApp notifications (optional)

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

WHATSAPP NOTIFICATIONS (OPTIONAL):
-----------------------------------

To enable WhatsApp notifications:

1. Get Twilio account (https://www.twilio.com)
2. Create .env file:
   sudo nano /opt/power-monitor/.env

3. Add your credentials:
   WHATSAPP_ENABLED=true
   WHATSAPP_PROVIDER=twilio
   TWILIO_ACCOUNT_SID=your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_FROM_NUMBER=whatsapp:+14155238886
   TWILIO_TO_NUMBER=whatsapp:+919876543210
   WHATSAPP_RATE_LIMIT_SECONDS=300

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
