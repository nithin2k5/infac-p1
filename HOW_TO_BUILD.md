# How to Build Customer Package

## Quick Build

```bash
python3 build_customer_package.py
```

## Create Archive

```bash
cd customer_package
tar -czf power-monitor-installer.tar.gz power-monitor/
```

## Send to Customer

Send file: `customer_package/power-monitor-installer.tar.gz`

---

## What Gets Built

- ✅ Compiled `.pyc` files (no source code)
- ✅ Automatic installer
- ✅ MySQL configuration wizard
- ✅ Customer documentation
- ❌ NO `.py` source files

---

## Customer Installation

```bash
tar -xzf power-monitor-installer.tar.gz
cd power-monitor
sudo ./install.sh
```

That's it!

---

See `README.md` for complete documentation.

