# MiniStatus

Lightweight, self-hosted service status dashboard for developers, homelabs, and small teams.

Built with Flask and SQLite. No Prometheus. No Grafana. Just clean uptime visibility.

## Features

- **Public Status Dashboard** - Clean, user-friendly status page showing only public-facing services
- **Service Status Tracking** - Manual and API-based status reporting
- **Systemd Service Sync** - Automatic synchronization with systemd services
- **Local Port Monitoring** - Real-time port status tracking
- **Remote Host Monitoring** - Monitor services on remote servers
- **Admin Panel** - Full-featured admin interface with secure authentication
- **Password Security** - bcrypt password hashing with in-app password management
- **Tag System** - Organize services with tags (public/private visibility control)
- **Auto-Tagging** - Automatic service tagging based on rules
- **RSS Feed** - Subscribe to status updates via RSS (`/feed.xml`)
- **CSRF Protection** - Built-in CSRF protection for all forms
- **Rate Limiting** - Protection against brute force attacks
- **Dark/Light Theme** - Automatic theme support
- **REST API** - Programmatic status reporting

## Quick Start

### Installation

```bash
sudo bash scripts/install.sh
```

The installer will:
- Install dependencies
- Set up virtual environment
- Configure systemd service
- Start the application

The app runs as a systemd service and auto-starts on boot.

### Access

- **Public Dashboard:** `http://YOUR_SERVER_IP:5000` - Clean status page for external users
- **RSS Feed:** `http://YOUR_SERVER_IP:5000/feed.xml` - Subscribe to status updates
- **Admin Panel:** `http://YOUR_SERVER_IP:5000/admin/login` - Full admin interface

**Default credentials:** `admin` / `admin123` (change via Settings → Change Password in admin panel)

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

# Public Dashboard Configuration (optional)
PUBLIC_REGION=US-East  # Region badge on public dashboard
PUBLIC_ENVIRONMENT=Production  # Environment badge (Production/Staging/Development)
```

### Security Features

- **Password Hashing:** Passwords in `.env` are automatically hashed using bcrypt when the app starts
- **Password Changes:** Change your password via the admin panel (Settings → Change Password) - no need to edit `.env` manually
- **Migration:** Existing plain text passwords are automatically converted to hashed passwords on first app startup
- **CSRF Protection:** All forms are protected against Cross-Site Request Forgery attacks
- **Rate Limiting:** Login attempts and API endpoints are rate-limited to prevent abuse
  - Login: 5 attempts per minute
  - API `/api/report`: 60 requests per minute

### YAML Configuration Files

Place configuration files in the `config/` directory:

- `config/auto_tag_rules.yaml` - Auto-tagging rules
- `config/quick_links.yaml` - Quick links panel
- `config/services.yaml` - Service definitions (optional)

## RSS Feed

Subscribe to status updates via RSS:

- **Feed URL:** `http://YOUR_SERVER_IP:5000/feed.xml`
- **Alternative URL:** `http://YOUR_SERVER_IP:5000/rss` (redirects to `/feed.xml`)

The RSS feed includes:
- Incident announcements (active and resolved)
- Service status changes
- Real-time updates

**Note:** Only public-facing incidents are included in the RSS feed.

## API

### Report Service Status

```bash
curl -X POST http://YOUR_SERVER_IP:5000/api/report \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"name":"nginx","status":"up","description":"Web server"}'
```

**Rate Limit:** 60 requests per minute

**Response:**
```json
{
  "message": "Service 'nginx' updated to 'up'"
}
```

### Testing the API

**Option 1: Use the Web UI (easiest - recommended)**

1. Log in to the admin panel
2. Go to **Settings → API Testing**
3. Fill in the form (service name, status, description)
4. Click **Send Request**
5. See the response instantly!

The API key is automatically loaded from your configuration, so you don't need to copy/paste it.

**Option 2: Use the test script**

```bash
# From the MiniStatus directory
./scripts/test_api.sh

# Or specify a different server
./scripts/test_api.sh 192.168.1.100 5000
```

**Option 3: Manual testing with curl**

1. **Find your API key:**
   ```bash
   grep API_KEY .env
   ```

2. **Test the API:**
   ```bash
   curl -X POST http://127.0.0.1:5000/api/report \
     -H "X-API-Key: YOUR_API_KEY_HERE" \
     -H "Content-Type: application/json" \
     -d '{"name":"my-service","status":"up","description":"My test service"}'
   ```

3. **What to expect:**
   - ✅ **Success (200):** `{"message": "Service 'my-service' updated to 'up'"}`
   - ❌ **Wrong API key (401):** `{"error": "Invalid API key"}`
   - ❌ **Missing data (400):** Error message about missing fields

4. **Check the result:**
   - Go to `http://127.0.0.1:5000/admin/dashboard`
   - You should see "my-service" in the service list!

**Option 3: Test from another computer**

Replace `127.0.0.1` with your server's IP address:
```bash
curl -X POST http://YOUR_SERVER_IP:5000/api/report \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"remote-service","status":"up"}'
```

### Scan Ports

```bash
curl http://YOUR_SERVER_IP:5000/api/ports/scan
```

**Note:** API endpoints are exempt from CSRF protection (they use API keys for authentication).

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
- Flask-WTF (for CSRF protection)
- Flask-Limiter (for rate limiting)

## Deployment

The application runs as a systemd service by default. The installer (`scripts/install.sh`) creates the service file at `/etc/systemd/system/ministatus.service`.

The service:
- Runs in background
- Auto-starts on boot
- Auto-restarts on failure
- Logs to systemd journal

To uninstall the service:

```bash
sudo bash scripts/uninstall.sh
```

## Public Dashboard

The public dashboard (`/`) is designed for external users and shows only **public-facing services**.

### Features

- **Clean Status Overview** - Global status banner with uptime percentage
- **Grouped by Tags** - Services organized by public-facing tags
- **Active Incidents** - Prominent display of unresolved incidents
- **RSS Subscription** - Subscribe to status updates via RSS feed
- **Region/Environment Badges** - Configurable via environment variables

### Making Services Public

To show services on the public dashboard:

1. Go to **Admin → Tags**
2. Create or edit a tag
3. Check **"Show on public dashboard"** (this makes the tag public-facing)
4. Tag your services with public tags

**Default Public Tags:**
- `core` - Core services
- `critical` - Critical services
- `external` - External dependencies
- `optional` - Optional services

**Note:** Services without public tags are **not shown** on the public dashboard (they remain visible only in the admin panel).

## Admin Panel

### Navigation Structure

**Public Section (always visible):**
- Dashboard - Public service status view
- Ports - Port monitoring dashboard

**Admin Section (requires login):**
- Admin Dashboard - Full admin control panel with system health info
- Remote Hosts - Remote service monitoring
- Tags - Service tag management (with public/private visibility)
- Auto-Tag Rules - Automatic tagging configuration
- Settings (collapsible menu)
  - Change Password - Update admin password via web UI
  - API Testing - Test API endpoints directly from the browser
- Logout - Sign out of admin session

### Managing Tags

Tags help organize services and control what appears on the public dashboard.

**Creating Public Tags:**
1. Go to **Admin → Tags**
2. Enter tag name and color
3. Check **"Show on public dashboard"** to make it public-facing
4. Click **Add**

**Tag Visibility:**
- **Public tags** - Services with these tags appear on the public dashboard
- **Private tags** - Services with only private tags are admin-only

**Default Tags:**
- `core` (public) - Core services
- `critical` (public) - Critical services  
- `external` (public) - External dependencies
- `optional` (public) - Optional services
- `networking` (private) - Network services
- `database` (private) - Database services
- `internal` (private) - Internal services
- `n8n` (private) - n8n automation services

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
├── app/                    # Application code
│   ├── routes/             # Flask blueprints
│   │   ├── admin.py        # Admin routes
│   │   ├── public.py       # Public dashboard & RSS feed
│   │   ├── api.py          # API endpoints
│   │   ├── sync.py         # Service synchronization
│   │   ├── remote.py       # Remote host monitoring
│   │   └── ports.py        # Port monitoring
│   ├── templates/          # Jinja2 templates
│   │   ├── public/         # Public dashboard templates
│   │   └── admin/           # Admin panel templates
│   ├── models.py           # Database models (Service, Tag, Incident)
│   ├── services/           # Business logic
│   ├── utils/              # Utilities
│   │   ├── password.py      # Password hashing utilities
│   │   └── helpers.py      # Helper functions
│   └── extensions.py       # Flask extensions (db, csrf, limiter)
├── config/                  # YAML configuration files
├── scripts/                 # Installation and utility scripts
│   ├── install.sh          # Installation script
│   ├── uninstall.sh        # Uninstallation script
│   ├── start.sh            # Start script
│   └── test_api.sh         # API testing script
├── tests/                   # Test files
├── run.py                   # Application entry point
├── .env.example             # Environment variables template
└── requirements.txt         # Python dependencies
```

## Database Schema

The application uses SQLite by default. Key tables:

- **Service** - Service status information
- **Tag** - Service tags (with `is_public` field for public dashboard visibility)
- **Incident** - Incident tracking
- **AutoTagRule** - Auto-tagging rules

**Migration:** The app automatically migrates the database schema on startup (e.g., adds `is_public` column to Tag table if missing).

## License

MIT License
