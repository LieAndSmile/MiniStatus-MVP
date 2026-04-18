# MiniStatus

**MiniStatus is the read-only operator console for the [polymarket-alerts](https://github.com/LieAndSmile/polymarket-alerts) engine.** It is not a general-purpose status dashboard.

Point `POLYMARKET_DATA_PATH` at your polymarket-alerts checkout so MiniStatus can read `alerts_log.csv`, `open_positions.csv`, `analytics.json`, and related artifacts. Strategy scorecard, portfolio P/L, AI simulation, Ops tools (positions, analytics, mirrors, dev), and CSV export are all session-authenticated.

Roadmap and pruning plan: [SCORECARD_AND_PRUNING_ROADMAP.md](https://github.com/LieAndSmile/polymarket-alerts/blob/main/docs/SCORECARD_AND_PRUNING_ROADMAP.md) (polymarket-alerts repo).

## Features

- **Polymarket console** — Live (portfolio), Scorecard, AI Simulation, Ops hub; safe-scope session, charts, export
- **Admin** — Login, change password, API key display (legacy JSON status API removed in Phase 5c Tier 3)
- **Security** — bcrypt passwords, CSRF on forms, rate-limited login
- **Themes** — Dark / light

## Quick Start

### Installation

```bash
sudo bash scripts/install.sh
```

The installer installs dependencies, creates a venv, configures systemd, and starts the app.

### Access

- **App root:** `http://YOUR_SERVER_IP:5000` → redirects to `/polymarket/scorecard` (login required)
- **Admin login:** `http://YOUR_SERVER_IP:5000/admin/login`

**Default credentials:** `admin` / `admin123` (change via **Settings → Change password**)

Legacy `/feed.xml` and `/rss` return **404** (Tier 3).

### Restarting the app

Restart the app (recommended; also applies a faster restart delay if needed):

```bash
./scripts/restart.sh
```

Or use systemd directly:

```bash
sudo systemctl status ministatus   # Check status
sudo systemctl restart ministatus  # Restart service
sudo systemctl stop ministatus     # Stop service
sudo journalctl -u ministatus -f   # View logs
```

**Note:** The service uses `RestartSec=2` so restarts complete in a few seconds. If you previously installed with an older version, run `./scripts/restart.sh` once to update the delay and restart.

### After pulling code changes

1. If **`requirements.txt`** changed, install deps (from project root, using your venv — often `scripts/venv`):

   ```bash
   ./scripts/venv/bin/pip install -r requirements.txt
   ```

2. Regenerate the **CI minimal** lockfile when `requirements.txt` changes (keeps GitHub Actions `test-ci-minimal` in sync):

   ```bash
   python3 scripts/sync_requirements_ci_minimal.py
   ```

3. Restart the app:

   ```bash
   ./scripts/restart.sh
   # or: sudo systemctl restart ministatus
   ```

**Polymarket integration** (optional): consumer contract, schema sync, and artifact expectations are documented in **`docs/POLYMARKET_INTEGRATION.md`**. Producer-side canonical schema is in **`polymarket-alerts/docs/INTEGRATION_CONTRACT.md`**.

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

# Polymarket Alerts integration (optional)
POLYMARKET_DATA_PATH=/path/to/polymarket-alerts  # Path to polymarket-alerts dir (alerts_log.csv, open_positions.csv, run_stats.csv, etc.)
```

For the full producer-side data contract that MiniStatus consumes, see:
- `polymarket-alerts/docs/INTEGRATION_CONTRACT.md`
- `polymarket-alerts/docs/CONTRACT_VERSION.md`

If the Polymarket pages show “CSV schema mismatch” or “No data” unexpectedly, first verify that `POLYMARKET_DATA_PATH` points at a live polymarket-alerts directory and that its CSV/JSON files conform to the current integration contract.

### Security

- Passwords in `.env` are bcrypt-hashed; use **Settings → Change password** in the UI.
- Forms use CSRF tokens; login is rate-limited (5/min).

## Development

```bash
git clone https://github.com/LieAndSmile/MiniStatus-MVP.git
cd MiniStatus-MVP
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Stack: Python 3.8+, Flask 3.1, Flask-WTF, Flask-Limiter, PyYAML, requests, bcrypt.

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

## Polymarket Integration

When `POLYMARKET_DATA_PATH` points to a polymarket-alerts directory, an admin-only **Polymarket** sub-app is available at `/polymarket` with six pages:

### Pages

| Page | Route | Description |
|------|-------|--------------|
| **Portfolio** | `/polymarket/portfolio` | Resolved bets, KPIs (wins, losses, net P/L, max drawdown), cumulative P/L chart, drawdown chart, filter (all/wins/losses), time window, sort, search, pagination, export |
| **Open Positions** | `/polymarket/positions` | Open positions from `open_positions.csv`, total cost, unrealized P/L, cluster exposure summary (top 5 by category), search, **filter by opened date** (All time / Last 30/90/180 days, or click a date to filter from that date), category filter, **track interesting** (star to mark positions; filter "Interesting only", sort "Interesting first"), sort, clickable Opened column header |
| **Risky** | `/polymarket/risky` | Positions matching the Risky strategy: edge ≥ 1%, gamma ≤ 0.94, expiry within 48h. **Excludes expired.** Tune via `RISKY_EDGE_MIN_PCT`, `RISKY_GAMMA_MAX`, `RISKY_EXPIRY_HOURS_MAX`. Results of resolved risky positions appear in **Analytics** (edge quality, timing, strategy cohort). |
| **Loss Lab** | `/polymarket/loss-lab` | Losses by category (politics, sports, crypto, etc.), time window filter |
| **Analytics** | `/polymarket/analytics` | Edge Quality, Timing, Strategy Cohort (with drawdown), MTM/Exit Study from `analytics.json`; refresh button |
| **Lifecycle** | `/polymarket/lifecycle` | Promote/kill verdicts per strategy from `lifecycle.json`; refresh button |
| **Loop / Dev** | `/polymarket/loop` | Debug candidates from CSV (default `debug_candidates.csv`; set `POLYMARKET_DEBUG_CSV` to match polymarket-alerts), time window filter, status filter (All/ALERT), sort, search, pagination, export, clickable dates for filtering |

### Features

- **Time window** – All time / Last 30 / 90 / 180 days (Portfolio, Loss Lab, Open Positions, Loop/Dev). **Click date cells** to filter from that date (Portfolio, Positions, Loop)
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
- Optional: `open_positions.csv` (run `update_open_positions.py` in polymarket-alerts), `polymarket_alerts.log` (health), `run_stats.csv` (per-run trend), debug candidates CSV (default `debug_candidates.csv`; configure `POLYMARKET_DEBUG_CSV` if different)
- CSV columns: `question`, `link`, `resolved`, `actual_result`, `pnl_usd`, `resolved_ts` or `ts`

### Open positions and tracking

To show open positions on the **Open Positions** page, run `update_open_positions.py` in polymarket-alerts:

```bash
cd polymarket-alerts
python3 update_open_positions.py          # Fetches live prices from CLOB API
python3 update_open_positions.py --no-live   # Uses last known prices only (no API)
python3 update_open_positions.py --dry-run   # Preview without writing
```

Creates `open_positions.csv` from unresolved alerts in `alerts_log.csv`. Columns: `market_id`, `question`, `side`, `shares`, `avg_price`, `cost_usd`, `current_mid`, `unrealized_pnl`, `last_updated`, `link`, `alert_ts` (for date filtering). Dates use **YYYY-MM-DD HH:MM** format across all tabs.

**Track interesting positions:** Use the star (★) in the "Track" column to mark positions you want to follow. Your list is stored in `interesting_positions.json` in the polymarket-alerts directory. Filter with **Track: Interesting only** or sort by **Interesting first** to keep them at the top until resolution.

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
├── app/
│   ├── routes/
│   │   ├── root.py         # / and legacy RSS stubs (404)
│   │   ├── admin.py        # Login, logout, password, help, API key
│   │   ├── polymarket.py   # Polymarket operator UI
│   │   └── error_handlers.py
│   ├── templates/          # Jinja2 (Polymarket + admin + base)
│   ├── utils/              # polymarket*.py, password, decorators, polymarket_health (incl. data-quality flags)
│   └── extensions.py       # csrf, limiter (no SQLAlchemy)
├── data/legacy/            # Optional: move old ministatus.db here if present on disk
├── scripts/
├── tests/
├── run.py
└── requirements.txt
```

**Database:** Tier 3 removed Flask-SQLAlchemy and product models. If an old `ministatus.db` exists on your server, you may move it to `data/legacy/ministatus.db.bak`; the app does not open it.

## License

MIT License
