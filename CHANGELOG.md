# Changelog

All notable changes to MiniStatus are documented in this file.

## [Unreleased]

### Added

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
