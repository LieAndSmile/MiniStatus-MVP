#!/bin/bash
# MiniStatus-MVP installation script.
# Installs deps into .venv/, writes a systemd unit, starts the service.

set -e

echo "=========================================="
echo "MiniStatus-MVP Installation"
echo "=========================================="
echo ""

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Wire up the secret-leak pre-commit hook for this clone (idempotent, harmless
# if .githooks/ is missing — git just runs no hooks).
if [ -d ".git" ] && [ -d ".githooks" ]; then
    git config core.hooksPath .githooks
fi

# Detect the unprivileged user we should own the venv as (so dev tooling
# without sudo can still rerun pytest, etc.). Fall back to root if none.
RUN_USER="${SUDO_USER:-root}"

echo "Step 1: Installing system dependencies..."
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv >/dev/null 2>&1
echo "✓ System dependencies installed"

echo ""
echo "Step 2: Creating virtual environment (.venv/)..."
if [ ! -d ".venv" ]; then
    sudo -u "$RUN_USER" python3 -m venv .venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

echo ""
echo "Step 3: Installing Python dependencies..."
sudo -u "$RUN_USER" .venv/bin/pip install --upgrade pip -q >/dev/null 2>&1
sudo -u "$RUN_USER" .venv/bin/pip install -r requirements.txt -q
echo "✓ Python dependencies installed"

echo ""
echo "Step 4: Creating .env file if it doesn't exist..."
if [ ! -f ".env" ]; then
    SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
    cat > .env <<EOF
# Flask config
FLASK_APP=run.py
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False

# Security - CHANGE THESE IN PRODUCTION!
SECRET_KEY=${SECRET_KEY}

# Admin auth - CHANGE THESE!
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123

# Polymarket Alerts integration (required for the Polymarket pages)
# POLYMARKET_DATA_PATH=/home/${RUN_USER}/polymarket-alerts
EOF
    chown "$RUN_USER":"$RUN_USER" .env
    echo "✓ .env file created with default values"
    echo "  ⚠️  IMPORTANT: Edit .env and change ADMIN_PASSWORD and POLYMARKET_DATA_PATH!"
else
    echo "✓ .env file already exists"
fi

echo ""
echo "Step 5: Creating systemd service..."
cat > /etc/systemd/system/ministatus.service <<EOF
[Unit]
Description=MiniStatus-MVP read-only operator console for polymarket-alerts
After=network.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${PROJECT_ROOT}
Environment="PATH=${PROJECT_ROOT}/.venv/bin"
ExecStart=${PROJECT_ROOT}/.venv/bin/gunicorn -c gunicorn.conf.py "run:app"
Restart=always
RestartSec=2
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo "✓ Systemd service created"

echo ""
echo "Step 6: Starting MiniStatus-MVP service..."
systemctl enable ministatus.service
systemctl restart ministatus.service
sleep 2

if systemctl is-active --quiet ministatus; then
    echo "✓ MiniStatus-MVP is now running!"
    echo ""
    echo "=========================================="
    echo "Installation Complete!"
    echo "=========================================="
    echo ""
    echo "Service Status:"
    systemctl status ministatus --no-pager -l | head -5
    echo ""
    IP=$(hostname -I | awk '{print $1}')
    echo "Access the dashboard at:"
    echo "  http://${IP}:5000"
    echo "  http://localhost:5000"
    echo ""
    echo "Admin login:"
    echo "  http://${IP}:5000/admin/login"
    echo "  Default credentials: admin / admin123"
    echo ""
    echo "⚠️  IMPORTANT: Change the default password (Settings → Change Password)."
    echo ""
    echo "Useful commands:"
    echo "  sudo systemctl status ministatus   # Check status"
    echo "  sudo systemctl restart ministatus  # Restart service"
    echo "  sudo systemctl stop ministatus     # Stop service"
    echo "  sudo journalctl -u ministatus -f   # View logs"
else
    echo "❌ Service failed to start. Check logs with:"
    echo "   sudo journalctl -u ministatus -n 50"
    exit 1
fi
