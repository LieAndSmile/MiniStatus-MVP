# Changelog

All notable changes to MiniStatus are documented in this file.

## [Unreleased]

### Added

- **Polymarket Analytics and Lifecycle tabs** – **Analytics** tab: Edge Quality (by edge bucket), Timing (by time-to-resolution bucket), Strategy Cohort (per strategy with sent/shadow, resolved, open, W/L, P/L, ROI, current/max drawdown %), and MTM/Exit Study (per-strategy avg price move at 1m, 5m, 30m, 2h, 1d). **Lifecycle** tab: promote/kill verdicts per strategy (PROMOTE / HOLD / KILL / INSUFFICIENT_DATA) with reasons and thresholds. Data from `analytics.json` and `lifecycle.json` in POLYMARKET_DATA_PATH. **Refresh** buttons on both tabs run `analytics_export.py` and `evaluate_strategy_lifecycle.py` in the data path to regenerate JSON (uses venv python when present). **File age:** Analytics and Lifecycle pages show "Last updated: X min/hours/days ago" from file mtime when available.
- **Polymarket Strategy dropdown** – Options are now dynamic: merged from `STRATEGY_OPTIONS` and any strategy IDs present in `analytics.json` strategy_cohort, so new strategies from polymarket-alerts appear in the dropdown without code changes. Fallback remains the full list: safe, safe_v2, same_day_probe, hold_*_probe, gamma_*_probe, mid_gamma, resolution_sprint.

- **Polymarket debug candidates filename** – Loop/Dev tab reads the debug candidates CSV by name from `POLYMARKET_DEBUG_CSV` (default: `debug_candidates.csv`), with fallback to `debug_candidates_v60.csv` and then any `debug_candidates*.csv` for backward compatibility. Set to match polymarket-alerts `DEBUG_CANDIDATES_CSV` if you use a custom name.
- **Polymarket date/time filtering** – Standardized date format (YYYY-MM-DD HH:MM) across Portfolio, Open Positions, and Loop/Dev. Click any date cell to filter from that date. Time window filter (All time / Last 30/90/180 days) on Open Positions and Loop/Dev. Clickable "Opened" column header for sort; "Filter by opened" bar above positions table.

- **Polymarket Open Positions filters** – Time window (All time, Last 30/90/180 days), category filter (Politics, Sports, Crypto, Other), sort (cost, P/L, date, question). `open_positions.csv` now includes `alert_ts` from `alerts_log.csv` for date filtering.

- **Polymarket cross-tab UX** – Active tab styling (background, font weight), mobile horizontal scroll for tabs, loading overlay when switching tabs or applying filters, empty states (e.g. "No open positions", "No resolved alerts yet")

- **Polymarket Losses tab** – Dedicated tab for full loss list with category filter (Politics, Sports, Crypto, Entertainment, Other), display filter (All time / Last 30/90/180 days), sort (biggest first, date, question, by category), search, pagination, and Export Losses CSV.

- **Polymarket Unresolved tab** – Open positions (alerts not yet resolved). Shows at-stake total, sort by alert date or days to resolution, search, pagination. Optional **live prices** – click "Load live prices" to fetch current YES price from Polymarket CLOB API and display Entry, Live, and Unrealized P/L columns.

- **Polymarket Edge/Gamma bands** – Performance analytics by edge band (0–0.5%, 0.5–1%, 1–1.5%, etc.) and gamma band (0.90–0.95, 0.95–0.97, etc.). Shows count, win rate, and P/L per band. Respects Display filter.

- **Polymarket Loop Summary improvements** – Status filter (All / ALERT only), sort (date, edge, question, ALERT first), clickable column headers (Time, Question, Edge, Status), improved pagination with page numbers. Event time formatted as "Mar 02, 2026 05:30 PM UTC". Direct links to Polymarket markets (from debug CSV link column).

- **Polymarket Loop Summary tab** – New tab in Polymarket admin page displays full data from `debug_candidates_v60.csv` (same as "Full data" in Telegram loop summary). Paginated table with search, export CSV. Tabs: Resolved Alerts | Losses | Unresolved | Loop Summary.

- **Polymarket pagination** - Resolved alerts table paginated (50 per page) with Previous/Next, page numbers, and "Showing X–Y of Z" for better UX with many resolved alerts

- **Per-run stats log** - `scripts/log_run_stats.py` appends stats snapshot after each polymarket-alerts run to `run_stats.csv`; MiniStatus reads it and shows "Per-Run Stats Trend" charts (resolved count, P/L over time) for trend analysis

- **Polymarket sort options** - Resolved list sortable by P/L (lowest/highest first), date (newest/oldest), question (A–Z, Z–A), result (YES/NO first) for easier data exploration

- **Polymarket Integration** - Admin-only dashboard for polymarket-alerts
  - Summary stats: total alerts, resolved, wins, losses, net P/L
  - Filter by wins/losses (All / Wins / Losses)
  - Display filter: All time / Last 30 / 90 / 180 days
  - Client-side search by question text
  - Refresh button to reload data
  - Export CSV: download filtered list (question, result, pnl_usd, link)
  - Health check: "polymarket-alerts last run: X hours ago" from `polymarket_alerts.log`
  - P/L chart: cumulative P/L over time (Chart.js line chart)
  - Requires `POLYMARKET_DATA_PATH` in `.env` pointing to polymarket-alerts directory

- **Production WSGI** - Gunicorn instead of Flask dev server. Config in `gunicorn.conf.py`; workers, bind, and timeout configurable via env.

- **Backfill script** - `scripts/backfill_resolved_ts.py` – fills missing `resolved_ts` from `ts` for resolved rows (improves date filters and P/L chart)

- **Retention script** - `scripts/retention_alerts_log.py`
  - Trims `alerts_log.csv` to keep only rows from last N days
  - Creates `.bak` backup before modifying
  - Usage: `python3 retention_alerts_log.py --days 90 [--dry-run]`
  - Designed to be copied to polymarket-alerts and run via cron

### Changed

- **Unified admin_required decorator** – All admin-protected routes now use shared `app.utils.decorators.admin_required`; removed duplicate definitions from admin.py and sync.py
- **Polymarket refactoring** – Added `_polymarket_configured_required` decorator for not-configured handling; `_get_data_path()` helper; `build_pagination()` and `_STATS_EMPTY` in polymarket utils; shared `polymarket_time_filter.html` macro for time window UI; simplified `_parse_filter_days()` to return `(filter_val, days_val, days)`
- **403 error handler** – `errors_bp` now registered in app; custom 403 page renders when access is forbidden

### Removed

- **Unused files** – `polymarket_placeholder.html`, `public/home.html`, `scan_systemd.html`, `static/dark.css`
- **Dead code** – `register_blueprints()` from routes/__init__.py; `_bucket()` from polymarket utils; orphaned helpers (get_all_quick_links, get_security_summary, get_public_holidays, etc.) from helpers.py
- **Duplicate PORT_LABELS** – Removed from ports route; port labels come from port data
- **YAML config references** – `quick_links.yaml` and `security_summary.yaml` removed from docs (features were unused)
