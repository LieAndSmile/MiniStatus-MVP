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
- **Polymarket Integration** - Admin-only dashboard for polymarket-alerts (Portfolio, Open Positions, Performance, Loss Lab, Loop/Dev; filters, search, charts, export, mtime caching)

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

Configuration is in `.env` file (auto-created during installation). 

**Note:** If you need to manually create the `.env` file, you can copy `.env.example` as a starting point:
```bash
cp .env.example .env
# Then edit .env with your settings
```

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

# Polymarket Alerts integration (optional)
POLYMARKET_DATA_PATH=/path/to/polymarket-alerts  # Path to polymarket-alerts dir (alerts_log.csv, open_positions.csv, run_stats.csv, etc.)
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

The application runs as a systemd service by default, using **Gunicorn** as the WSGI server (production-ready, not the Flask development server). The installer (`scripts/install.sh`) creates the service file at `/etc/systemd/system/ministatus.service`.

The service:
- Runs in background via Gunicorn (2 workers by default)
- Auto-starts on boot
- Auto-restarts on failure
- Logs to systemd journal

Optional env vars for Gunicorn: `GUNICORN_WORKERS` (default 2), `GUNICORN_LOG_LEVEL` (default info).

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
- Polymarket - Portfolio, Open Positions, Performance, Loss Lab, Loop/Dev (filters, search, charts, export)
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

## Polymarket Integration

When `POLYMARKET_DATA_PATH` points to a polymarket-alerts directory, an admin-only **Polymarket** sub-app is available at `/polymarket` with five pages:

### Pages

| Page | Route | Description |
|------|-------|--------------|
| **Portfolio** | `/polymarket/portfolio` | Resolved bets, KPIs (wins, losses, net P/L, max drawdown), cumulative P/L chart, drawdown chart, filter (all/wins/losses), time window, sort, search, pagination, export |
| **Open Positions** | `/polymarket/positions` | Open positions from `open_positions.csv`, total cost, unrealized P/L, cluster exposure summary (top 5 by category), search, **filter by opened date** (All time / Last 30/90/180 days, or click a date to filter from that date), category filter, sort, clickable Opened column header |
| **Performance** | `/polymarket/performance` | Expectancy by edge bands (0–0.5%, 0.5–1%, 1–2%, 2%+) and gamma bands; time window filter |
| **Loss Lab** | `/polymarket/loss-lab` | Losses by category (politics, sports, crypto, etc.), time window filter |
| **Loop / Dev** | `/polymarket/loop` | Debug candidates from `debug_candidates_v60.csv`, time window filter, status filter (All/ALERT), sort, search, pagination, export, clickable dates for filtering |

### Features

- **Time window** – All time / Last 30 / 90 / 180 days (Portfolio, Performance, Loss Lab, Open Positions, Loop/Dev). **Click date cells** to filter from that date (Portfolio, Positions, Loop)
- **Search** – Client-side search by question text (Portfolio, Positions, Loop)
- **Sticky table headers** – Headers stay visible when scrolling
- **mtime caching** – CSV reads are cached; cache invalidates when files change
- **Charts** – Cumulative P/L, drawdown, per-run stats trend (Chart.js)
- **Export CSV** – Resolved list, Loop Summary
- **Health check** – "polymarket-alerts last run: X ago" from `polymarket_alerts.log`
- **CSV schema validation** – Clear "CSV schema mismatch" banner when `alerts_log.csv` is invalid
- **Cross-tab UX** – Active tab styling, mobile horizontal scroll, loading overlay when switching tabs/filters, empty states (e.g. "No open positions")

### Requirements

- polymarket-alerts directory with `alerts_log.csv` (required)
- Optional: `open_positions.csv` (run `update_open_positions.py` in polymarket-alerts), `polymarket_alerts.log` (health), `run_stats.csv` (per-run trend), `debug_candidates_v60.csv` (Loop page)
- CSV columns: `question`, `link`, `resolved`, `actual_result`, `pnl_usd`, `resolved_ts` or `ts`

### Open positions

To show open positions on the **Open Positions** page, run `update_open_positions.py` in polymarket-alerts:

```bash
cd polymarket-alerts
python3 update_open_positions.py          # Fetches live prices from CLOB API
python3 update_open_positions.py --no-live   # Uses last known prices only (no API)
python3 update_open_positions.py --dry-run   # Preview without writing
```

Creates `open_positions.csv` from unresolved alerts in `alerts_log.csv`. Columns: `market_id`, `question`, `side`, `shares`, `avg_price`, `cost_usd`, `current_mid`, `unrealized_pnl`, `last_updated`, `link`, `alert_ts` (for date filtering). Dates use **YYYY-MM-DD HH:MM** format across all tabs.

### Backfill resolved_ts

For older rows that are resolved but lack `resolved_ts`, backfill from `ts`:

```bash
cd polymarket-alerts
python3 backfill_resolved_ts.py --dry-run   # Preview
python3 backfill_resolved_ts.py              # Backfill (creates .bak backup)
```

Copy `scripts/backfill_resolved_ts.py` from MiniStatus.

### Retention script

A retention script is provided to trim old rows from `alerts_log.csv`:

```bash
# From polymarket-alerts directory
python3 retention_alerts_log.py --days 90 --dry-run   # Preview
python3 retention_alerts_log.py --days 90             # Trim (creates .bak backup)
```

Copy `scripts/retention_alerts_log.py` to your polymarket-alerts directory. Optional cron: `0 3 * * 0 cd /path/to/polymarket-alerts && python3 retention_alerts_log.py --days 90`

### Per-run stats log (trend analysis)

Append a stats snapshot after each polymarket-alerts run to enable trend charts:

```bash
# Copy script to polymarket-alerts
cp /path/to/MiniStatus-MVP/scripts/log_run_stats.py /path/to/polymarket-alerts/

# Run after resolution_tracker (e.g. in same timer or cron)
cd /path/to/polymarket-alerts
./venv/bin/python resolution_tracker.py --once && python3 log_run_stats.py
```

Creates `run_stats.csv` with columns: `ts`, `resolved`, `wins`, `losses`, `total_pnl`, `alerts_total`. MiniStatus reads this and shows "Per-Run Stats Trend" charts (resolved count, P/L over time).

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
│   │   ├── ports.py        # Port monitoring
│   │   ├── polymarket.py   # Polymarket alerts integration
│   │   └── error_handlers.py  # 403 and other error handlers
│   ├── templates/          # Jinja2 templates
│   │   ├── public/         # Public dashboard templates
│   │   ├── admin/          # Admin panel templates
│   │   ├── polymarket_nav.html      # Shared Polymarket tab navigation
│   │   └── polymarket_time_filter.html  # Shared time window filter macro
│   ├── models.py           # Database models (Service, Tag, Incident)
│   ├── services/           # Business logic
│   ├── utils/              # Utilities
│   │   ├── decorators.py   # admin_required and shared decorators
│   │   ├── password.py    # Password hashing utilities
│   │   ├── helpers.py     # Helper functions (system stats, identity)
│   │   ├── polymarket.py  # Polymarket CSV/log parsing
│   │   ├── ports.py       # Port scanning utilities
│   │   └── auto_tag.py    # Auto-tagging rules
│   └── extensions.py      # Flask extensions (db, csrf, limiter)
├── config/                 # YAML configuration files
├── scripts/                # Installation and utility scripts
│   ├── install.sh          # Installation script
│   ├── uninstall.sh        # Uninstallation script
│   ├── start.sh            # Start script
│   ├── test_api.sh         # API testing script
│   ├── retention_alerts_log.py  # Trim old rows from polymarket alerts_log.csv
│   ├── backfill_resolved_ts.py   # Backfill resolved_ts from ts for date filters
│   ├── log_run_stats.py          # Append per-run stats to run_stats.csv for trend analysis
│   └── deploy_to_vm.sh           # Deploy to VM (rsync + restart); set VM_HOST, VM_USER, VM_PATH in .env
├── tests/                  # Test files
├── run.py                  # Application entry point
├── .env.example            # Environment variables template
└── requirements.txt        # Python dependencies
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
