# Changelog

All notable changes to MiniStatus are documented in this file.

## [Unreleased]

### Added

- **Polymarket Integration** - Admin-only dashboard for polymarket-alerts
  - Summary stats: total alerts, resolved, wins, losses, net P/L
  - Filter by wins/losses (All / Wins / Losses)
  - Display filter: All time / Last 30 / 90 / 180 days
  - Client-side search by question text
  - Refresh button to reload data
  - Export CSV: download filtered list (question, result, pnl_usd, link)
  - Health check: "polymarket-alerts last run: X hours ago" from `polymarket_alerts.log`
  - Requires `POLYMARKET_DATA_PATH` in `.env` pointing to polymarket-alerts directory

- **Retention script** - `scripts/retention_alerts_log.py`
  - Trims `alerts_log.csv` to keep only rows from last N days
  - Creates `.bak` backup before modifying
  - Usage: `python3 retention_alerts_log.py --days 90 [--dry-run]`
  - Designed to be copied to polymarket-alerts and run via cron
