#!/bin/bash
set -euo pipefail

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Run: sudo $0"
  exit 1
fi

RUN_USER="${SUDO_USER:-}"
if [[ -z "$RUN_USER" || "$RUN_USER" == "root" ]]; then
  echo "Run this from sudo after logging in as your normal user, e.g.: sudo ./scripts/install-systemd-service.sh"
  echo "Or set: export SUDO_USER=yourname"
  exit 1
fi

HOME_DIR=$(getent passwd "$RUN_USER" | cut -d: -f6)
REPO="${HOME_DIR}/infac-p1"
VENV_PY="${REPO}/venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Missing venv interpreter: $VENV_PY"
  echo "Create venv first: cd $REPO && /usr/bin/python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

cat > /etc/systemd/system/power-monitor.service << EOF
[Unit]
Description=Power Monitor Service - 24/7 EB and Generator Monitoring
After=network-online.target mariadb.service
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${REPO}
ExecStart=${VENV_PY} -m src.background_monitor
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable power-monitor.service
systemctl restart power-monitor.service
echo "Enabled at boot and started now. Check: sudo systemctl status power-monitor"
