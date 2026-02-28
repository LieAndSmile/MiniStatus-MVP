# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **MiniStatus integration** – Data files (`alerts_log.csv`, `polymarket_alerts.log`) can be read by MiniStatus for an admin dashboard (stats, filters, export, health check). Set `POLYMARKET_DATA_PATH` in MiniStatus's `.env` to this directory.
- **Retention script** – `retention_alerts_log.py` (copy from MiniStatus) trims old rows from `alerts_log.csv`. Use `--days 90` for 90-day retention; creates `.bak` backup before modifying.

### Changed
- **resolution_tracker**: Add clickable Polymarket links to each item in Resolved today summary (Telegram HTML).
- **resolution_tracker**: Fix malformed labels (token_id, numeric values) in Resolved today – use validated question/market or slug from link, fallback to "Market (ID...)".
- **resolution_tracker**: Add win/loss summary at top of Resolved today (Wins | Losses | Net P/L).
- **resolution_tracker**: Fix float conversion when yes_price/best_ask contains malformed data (misaligned CSV).
- **resolution_tracker**: Send only win/loss summary; omit full list to stay under Telegram limit.
- **resolution_tracker**: Hybrid format – summary + first 20 items (losses first) + "...and N more".
- **resolution_tracker**: Fixed outcome tracking to use token_id instead of title. Now looks up market by clob_token_ids API param, maps our token to the correct outcome index in clobTokenIds/outcomePrices, and checks if that outcome won (resolves multi-outcome markets correctly). Falls back to title search when token lookup fails. Validates token_id format (skips URLs/malformed). Fixes resolved None handling and datetime deprecation.

### Added (earlier)
- Initial project setup
