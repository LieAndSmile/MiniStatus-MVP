# MiniStatus

**MiniStatus is the read-only operator console for the [polymarket-alerts](https://github.com/LieAndSmile/polymarket-alerts) engine.** It is not a general-purpose status dashboard.

Point `POLYMARKET_DATA_PATH` at your polymarket-alerts checkout so MiniStatus can read `alerts_log.csv`, `open_positions.csv`, `analytics.json`, and related artifacts. Strategy scorecard, portfolio P/L, AI simulation, Tools hub (positions, analytics, mirrors, dev; `/polymarket/ops`), and CSV export are all session-authenticated.

Roadmap and pruning plan: [SCORECARD_AND_PRUNING_ROADMAP.md](https://github.com/LieAndSmile/polymarket-alerts/blob/main/docs/SCORECARD_AND_PRUNING_ROADMAP.md) (polymarket-alerts repo).

## Features

- **Polymarket console** — Four primary destinations (**Live**, **Scorecard**, **AI Simulation**, **Tools**) plus a Tools hub at `/polymarket/ops` that opens the secondary pages: Open Positions, Risky, Analytics, Loss Lab, Lifecycle, AI Performance, Mirror Portfolio, Mirror Alerts, Loop / Dev. Safe-scope session, charts, CSV export.
- **AI tabs** — **AI Simulation** (per-strategy bankroll sim from `ai_sim_bankroll.json`) and **AI Performance** (lift tiles, recent producer-side AI blocks, link back into the simulation).
- **Mirror tools** — **Mirror Portfolio** (ledger / P&L from `mirror_portfolio.json`) and **Mirror Alerts** (manage up to 20 wallets, per-wallet Telegram on/off, writes `mirror_watch_config.json`).
- **Admin** — Login, change password. Legacy JSON status API and SQLite stack were removed in 1.7.0 (Phase 5c Tier 3); the app no longer opens any local DB.
- **Security** — bcrypt passwords, CSRF on forms, rate-limited login.
- **Themes** — Dark / light.

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

1. If **`requirements.txt`** changed, install deps into the project venv (`.venv/`):

   ```bash
   ./.venv/bin/pip install -r requirements.txt
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

# Polymarket Alerts integration (required for the Polymarket pages)
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

When `POLYMARKET_DATA_PATH` points to a polymarket-alerts directory, an admin-only **Polymarket** sub-app is available at `/polymarket`. The sidebar groups pages into **Main**, **Tools**, **Mirrors**, and **Diagnostics**; the four primary tabs at the top are Live, Scorecard, AI Simulation, and Tools.

### Pages

**Main**

| Page | Route | Description |
|------|-------|--------------|
| **Live (Portfolio)** | `/polymarket/portfolio` | Resolved bets, KPIs (wins, losses, net P/L, max drawdown), cumulative P/L and drawdown charts, filter (all/wins/losses), time window, sort, search, pagination, export. |
| **Scorecard** | `/polymarket/scorecard` | Per-strategy roll-up: resolved count, win rate, ROI, P/L, drawdown. Sortable columns, time-window filter (`?days=`), strategy dropdown filter. |
| **AI Simulation** | `/polymarket/ai-simulation` | Per-strategy AI sim bankroll from `ai_sim_bankroll.json`; cross-link to AI Performance. |
| **Tools (Overview)** | `/polymarket/ops` | Hub page; one-click into all secondary tabs grouped by purpose (portfolio & risk, reports & analysis, AI, engine/debug, mirroring). |

**Tools (secondary)**

| Page | Route | Description |
|------|-------|--------------|
| **Open Positions** | `/polymarket/positions` | Open positions from `open_positions.csv`, total cost, unrealized P/L, cluster exposure summary (top 5 by category), search, **filter by opened date** (All time / Last 30/90/180 days, or click a date to filter from that date), category filter, **track interesting** (star to mark positions; filter "Interesting only", sort "Interesting first"), sort, clickable Opened column header. |
| **Risky** | `/polymarket/risky` | Positions matching the Risky preset: edge ≥ 1%, gamma ≤ 0.94, expiry within 48h. **Excludes expired.** Tune via `RISKY_EDGE_MIN_PCT`, `RISKY_GAMMA_MAX`, `RISKY_EXPIRY_HOURS_MAX`. Page shows **Now** vs **History** sections, qualifying / hit-rate / avg P/L summary, empty-state CTA to a Loose preset, and a **Track** column (same toggle as Open Positions). |
| **Analytics** | `/polymarket/analytics` | Edge Quality, Timing, Strategy Cohort (with drawdown), MTM / Exit Study from `analytics.json`; **At a glance** hero, win-rate bar columns, all-strategies / strategy-filter badges. **Δ vs previous export** — diffs against `analytics.prev.json` (resolved counts, "was:" insight lines, optional cohort ROI / 2h drift when a strategy filter is set). Refresh button re-runs the producer export. |
| **Loss Lab** | `/polymarket/loss-lab` | Losses by category (politics, sports, crypto, etc.) with filter chips, biggest-driver cards (category / strategy / timing), monthly sparkline bars above the trend table, time-window filter. |
| **Lifecycle** | `/polymarket/lifecycle` | Promote/kill verdicts per strategy from `lifecycle.json`; refresh button. |
| **AI Performance** | `/polymarket/ai-performance` | TL;DR strip, tooltips and sample sizes on lift tiles, recent producer-side AI-blocked rows, details table, link to AI Simulation. |

**Mirrors**

| Page | Route | Description |
|------|-------|--------------|
| **Mirror Portfolio** | `/polymarket/mirror-portfolio` | Ledger / P&L from `mirror_portfolio.json`; **Refresh from API** re-runs the mirror export. |
| **Mirror Alerts** | `/polymarket/mirror-alerts` | Manage up to 20 watched wallets with labels and per-wallet Telegram on/off; writes `mirror_watch_config.json` for the producer-side `jobs/mirror_watch.py` timer. |

**Diagnostics**

| Page | Route | Description |
|------|-------|--------------|
| **Loop / Dev** | `/polymarket/loop` | Debug candidates from CSV (default `debug_candidates.csv`; set `POLYMARKET_DEBUG_CSV` to match polymarket-alerts), time window filter, status filter (All/ALERT), sort, search, pagination, export, clickable dates for filtering. |

### Cross-page features

- **Time window** – All time / Last 30 / 90 / 180 days (Portfolio, Loss Lab, Open Positions, Loop/Dev, Scorecard). **Click date cells** to filter from that date (Portfolio, Positions, Loop).
- **Strategy filter** – Most pages accept `?strategy=<id>`; the dropdown is filled from strategy IDs found in the data.
- **Search** – Client-side search by question text (Portfolio, Positions, Loop).
- **Sticky table headers** – Headers stay visible when scrolling; mobile horizontal scroll.
- **mtime caching** – CSV/JSON reads are cached; cache invalidates when files change.
- **Charts** – Cumulative P/L, drawdown, per-run stats trend (Chart.js).
- **Export CSV** – Resolved list, Loop Summary, debug candidates.
- **Health & freshness** – "polymarket-alerts last run: X ago" from `polymarket_alerts.log`; per-artifact age strip.
- **Data-quality flags** – Yellow banner when `analytics.json` and `alerts_log.csv` disagree on a strategy's resolved count (suppressed when the CSV itself fails schema validation, so the red error wins).
- **CSV schema validation** – Clear "CSV schema mismatch" banner when `alerts_log.csv` headers don't match the producer-side contract.
- **Shared header partial** – Risky, Loss Lab, Analytics, AI Performance, AI Simulation share `_partials/polymarket_page_header.html` (title + action slot + breadcrumbs).
- **Cross-tab UX** – Active tab styling, loading overlay when switching tabs/filters, empty states with CTAs.

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
│   │   ├── root.py             # / → scorecard redirect; /feed.xml + /rss → 404
│   │   ├── admin.py            # Login, logout, change password, help
│   │   ├── polymarket.py       # Polymarket operator UI (all /polymarket/* routes)
│   │   └── error_handlers.py
│   ├── templates/
│   │   ├── _partials/          # Shared Jinja partials (e.g. polymarket_page_header.html)
│   │   ├── admin/              # change_password.html, help.html
│   │   ├── base.html           # Sidebar (Main / Tools / Mirrors / Diagnostics) + top tabs
│   │   ├── login.html
│   │   ├── 403.html
│   │   └── polymarket*.html    # one template per Polymarket page
│   ├── utils/
│   │   ├── decorators.py
│   │   ├── password.py         # bcrypt hashing helpers
│   │   ├── polymarket.py       # Main data-loading entry points
│   │   ├── polymarket_constants.py
│   │   ├── polymarket_format.py
│   │   ├── polymarket_health.py# Freshness + get_data_quality_flags
│   │   ├── polymarket_io.py    # CSV/JSON readers with mtime cache
│   │   └── polymarket_parse.py
│   └── extensions.py           # csrf, limiter only (no SQLAlchemy)
├── docs/
│   ├── POLYMARKET_INTEGRATION.md
│   ├── MINISTATUS_INTEGRATION.md
│   ├── SECONDARY_TABS_UX_PLAN.md
│   └── DUCKDB_MIGRATION_PLAN.md
├── scripts/
│   ├── install.sh              # systemd setup; uses .venv/, runs as $SUDO_USER
│   ├── uninstall.sh
│   ├── restart.sh              # quick `systemctl restart` wrapper
│   ├── analyze_losses_by_category.py
│   ├── backfill_resolved_ts.py
│   ├── log_run_stats.py
│   ├── retention_alerts_log.py
│   └── sync_requirements_ci_minimal.py
├── tests/                      # pytest; ~13 test_*.py files
├── AGENTS.md                   # Rules for AI agents working in this repo
├── CHANGELOG.md
├── run.py                      # Entry point (uses gunicorn in production)
├── gunicorn.conf.py
├── requirements.txt
└── requirements-ci-minimal.txt # Lock for CI minimal job; sync via scripts/sync_requirements_ci_minimal.py
```

**Database:** v1.7.0 (Phase 5c Tier 3) removed Flask-SQLAlchemy and the product models. The app does not open any local SQLite DB. All data comes from CSV/JSON files in `POLYMARKET_DATA_PATH`.

## License

MIT License
