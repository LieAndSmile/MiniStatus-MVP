#!/bin/bash
# Deploy MiniStatus to VM and restart the service.
# Usage: ./scripts/deploy_to_vm.sh
# Set VM_HOST, VM_USER, VM_PATH in .env or environment.

set -e
cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

# Load .env if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

VM_HOST="${VM_HOST:-192.168.0.110}"
VM_USER="${VM_USER:-ubuntu}"
VM_PATH="${VM_PATH:-/home/ubuntu/MiniStatus-MVP}"

echo "Deploying to ${VM_USER}@${VM_HOST}:${VM_PATH}"

# Sync files (exclude venv, .git, __pycache__, etc.)
rsync -avz --delete \
  --exclude 'venv/' \
  --exclude '.git/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude '*.db' \
  --exclude 'instance/' \
  --exclude '.cursor/' \
  --exclude 'node_modules/' \
  "$PROJECT_ROOT/" "${VM_USER}@${VM_HOST}:${VM_PATH}/"

# Restart service on VM
ssh "${VM_USER}@${VM_HOST}" "sudo systemctl restart ministatus" 2>/dev/null || {
  echo "Warning: systemctl restart failed. Run manually on VM: sudo systemctl restart ministatus"
}

echo "Deploy complete. App should be live at http://${VM_HOST}:5000"
