#!/usr/bin/env bash
# Restart the MiniStatus app (systemd Gunicorn on port 5000).
# Run from project root or scripts/:
#   ./scripts/restart.sh
#   or: bash scripts/restart.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_FILE="/etc/systemd/system/ministatus.service"

if ! systemctl is-active --quiet ministatus 2>/dev/null; then
  echo "Ministatus service is not running. Start it with: sudo systemctl start ministatus"
  exit 1
fi

# Optionally speed up future restarts: change RestartSec from 10 to 2 (only if we have sudo)
if [ -f "$SERVICE_FILE" ] && grep -q 'RestartSec=10' "$SERVICE_FILE" 2>/dev/null; then
  if sudo sed -i 's/RestartSec=10/RestartSec=2/' "$SERVICE_FILE" 2>/dev/null; then
    echo "Updated RestartSec to 2s for faster restarts."
    sudo systemctl daemon-reload
  fi
fi

echo "Restarting ministatus..."
sudo systemctl restart ministatus
sleep 1
if systemctl is-active --quiet ministatus; then
  echo "✓ MiniStatus is running on http://localhost:5000"
else
  echo "✗ Service may have failed. Check: sudo journalctl -u ministatus -n 20"
  exit 1
fi
