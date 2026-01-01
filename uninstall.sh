#!/bin/bash
# MiniStatus-MVP Uninstallation Script

set -e

echo "=========================================="
echo "MiniStatus-MVP Uninstallation"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

echo "Stopping and removing service..."
systemctl stop ministatus.service 2>/dev/null || true
systemctl disable ministatus.service 2>/dev/null || true
rm -f /etc/systemd/system/ministatus.service
systemctl daemon-reload
echo "✓ Service removed"

echo ""
echo "Service has been removed."
echo "Note: Application files and database are still in the installation directory."
echo "To completely remove, delete the MiniStatus-MVP directory."

