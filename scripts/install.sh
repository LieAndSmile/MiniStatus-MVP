#!/bin/bash
# MiniStatus-MVP Installation Script
# This script installs and sets up MiniStatus-MVP to run automatically

set -e

echo "=========================================="
echo "MiniStatus-MVP Installation"
echo "=========================================="
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

echo "Step 1: Installing system dependencies..."
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv >/dev/null 2>&1
echo "✓ System dependencies installed"

echo ""
echo "Step 2: Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

echo ""
echo "Step 3: Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip -q >/dev/null 2>&1
pip install flask flask_sqlalchemy python-dotenv psutil PyYAML requests -q
echo "✓ Python dependencies installed"
deactivate

echo ""
echo "Step 4: Creating .env file if it doesn't exist..."
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# Flask config
FLASK_APP=run.py
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False

# Security - CHANGE THESE IN PRODUCTION!
SECRET_KEY=$(openssl rand -hex 32)

# Admin auth - CHANGE THESE!
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123

# API
API_KEY=supersecret
EOF
    # Generate a random secret key
    SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s|SECRET_KEY=\$(openssl rand -hex 32)|SECRET_KEY=$SECRET_KEY|" .env
    echo "✓ .env file created with default values"
    echo "  ⚠️  IMPORTANT: Edit .env and change ADMIN_PASSWORD and API_KEY!"
else
    echo "✓ .env file already exists"
fi

echo ""
echo "Step 5: Creating systemd service..."
cat > /etc/systemd/system/ministatus.service << EOF
[Unit]
Description=MiniStatus-MVP Service Status Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$SCRIPT_DIR/venv/bin"
ExecStart=$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/run.py
Restart=always
RestartSec=10
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
systemctl start ministatus.service
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
    echo "Access the dashboard at:"
    IP=$(hostname -I | awk '{print $1}')
    echo "  http://$IP:5000"
    echo "  http://localhost:5000"
    echo ""
    echo "Admin Panel:"
    echo "  http://$IP:5000/admin/login"
    echo ""
    echo "Default credentials:"
    echo "  Username: admin"
    echo "  Password: admin123"
    echo ""
    echo "⚠️  IMPORTANT: Change the default password in .env file!"
    echo ""
    echo "Useful commands:"
    echo "  sudo systemctl status ministatus  # Check status"
    echo "  sudo systemctl restart ministatus # Restart service"
    echo "  sudo systemctl stop ministatus     # Stop service"
    echo "  sudo journalctl -u ministatus -f  # View logs"
else
    echo "❌ Service failed to start. Check logs with:"
    echo "   sudo journalctl -u ministatus -n 50"
    exit 1
fi

