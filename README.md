# MiniStatus

Lightweight, self-hosted service status dashboard for developers, homelabs, and small teams.

Built with Flask and SQLite. No Prometheus. No Grafana. Just clean uptime visibility.

## Features

- Service status tracking (manual and API)
- Systemd service sync
- Local port monitoring
- Remote host monitoring
- Admin panel with secure authentication (bcrypt password hashing)
- Password management via web UI
- Auto-tagging system
- Dark/Light theme support
- REST API for status reporting

## Quick Start

### Installation

```bash
sudo bash install.sh
```

The installer will:
- Install dependencies
- Set up virtual environment
- Configure systemd service
- Start the application

The app runs as a systemd service and auto-starts on boot.

### Access

- Public dashboard: `http://YOUR_SERVER_IP:5000`
- Admin panel: `http://YOUR_SERVER_IP:5000/admin/login`

Default credentials: `admin` / `admin123` (change via Settings → Change Password in admin panel)

**Important:** Passwords are automatically hashed using bcrypt for security. You can change your password through the admin panel's Settings menu.

### Service Management

```bash
sudo systemctl status ministatus   # Check status
sudo systemctl restart ministatus  # Restart service
sudo systemctl stop ministatus     # Stop service
sudo journalctl -u ministatus -f   # View logs
```

## Configuration

Configuration is in `.env` file (auto-created during installation):

```env
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
SECRET_KEY=your-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-password-hash  # Automatically hashed with bcrypt
API_KEY=your-api-key
```

### Security Notes

- **Password Hashing:** Passwords in `.env` are automatically hashed using bcrypt when the app starts
- **Password Changes:** Change your password via the admin panel (Settings → Change Password) - no need to edit `.env` manually
- **Migration:** Existing plain text passwords are automatically converted to hashed passwords on first app startup
- **Manual Edit:** If you manually edit `ADMIN_PASSWORD` in `.env`, it will be automatically hashed on the next app restart

### YAML Configuration Files

Place configuration files in the `config/` directory:

- `config/auto_tag_rules.yaml` - Auto-tagging rules
- `config/quick_links.yaml` - Quick links panel
- `config/services.yaml` - Service definitions (optional)

## API

### Report Service Status

```bash
curl -X POST http://YOUR_SERVER_IP:5000/api/report \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"name":"nginx","status":"up","description":"Web server"}'
```

### Scan Ports

```bash
curl http://YOUR_SERVER_IP:5000/api/ports/scan
```

## Development

### Manual Setup

```bash
# Clone repository
git clone https://github.com/LieAndSmile/MiniStatus-MVP.git
cd MiniStatus-MVP

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
python run.py
```

### Requirements

- Python 3.8+
- Flask 3.1.0
- SQLAlchemy 2.0.40
- psutil, PyYAML, requests
- bcrypt (for password hashing)

## Deployment

The application runs as a systemd service by default. The installer (`install.sh`) creates the service file at `/etc/systemd/system/ministatus.service`.

The service:
- Runs in background
- Auto-starts on boot
- Auto-restarts on failure
- Logs to systemd journal

To uninstall the service:

```bash
sudo bash uninstall.sh
```

## Admin Panel

### Navigation Structure

**Public Section (always visible):**
- Dashboard - Public service status view
- Ports - Port monitoring dashboard

**Admin Section (requires login):**
- Admin Dashboard - Full admin control panel
- Remote Hosts - Remote service monitoring
- Tags - Service tag management
- Auto-Tag Rules - Automatic tagging configuration
- Settings (collapsible menu)
  - Change Password - Update admin password via web UI
- Logout - Sign out of admin session

### Changing Your Password

1. Log in to the admin panel
2. Click **Settings** in the sidebar (gear icon)
3. Click **Change Password**
4. Enter your current password and new password
5. Click **Change Password**

The new password will be automatically hashed and saved. No need to restart the application.

## Project Structure

```
MiniStatus-MVP/
├── app/              # Application code
│   ├── routes/       # Flask blueprints
│   ├── models.py     # Database models
│   ├── services/     # Business logic
│   └── utils/        # Utilities
│       └── password.py  # Password hashing utilities
├── config/           # YAML configuration files
├── run.py            # Application entry point
├── install.sh        # Installation script
└── requirements.txt  # Python dependencies
```

## License

MIT License
