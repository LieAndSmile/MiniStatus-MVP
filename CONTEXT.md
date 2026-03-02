# Project Context

Reference this file in new chats (`@CONTEXT.md`) so the AI has project context.

## Overview

Two related projects:

1. **MiniStatus-MVP** – Flask status dashboard (this repo)
2. **polymarket-alerts** – Telegram alerts for Polymarket markets (separate repo)

Both run on the same VM. MiniStatus reads polymarket-alerts data via `POLYMARKET_DATA_PATH` in `.env`.

## VM Workflow

- **Workspace is on the VM** – edits are saved directly, no deploy step
- **After code changes:** `sudo systemctl restart ministatus`
- **polymarket-alerts** runs separately (systemd timer for resolution_tracker)

## Polymarket Integration

- Admin-only page at `/polymarket` with sub-nav: Portfolio, Open Positions, Performance, Loss Lab, Loop/Dev
- Reads from polymarket-alerts dir: `alerts_log.csv`, `polymarket_alerts.log`, `run_stats.csv` (optional), `open_positions.csv`, `debug_candidates_v60.csv`
- Features: summary stats, filter (All/Wins/Losses), time window (All time / 30/90/180 days), sort options, pagination (50/page), search, export CSV, P/L chart, per-run stats trend, Loop Summary tab
- Cross-tab UX: active tab styling, mobile scroll, loading overlay, empty states
- Shared templates: `polymarket_nav.html`, `polymarket_time_filter.html`

## Scripts (in MiniStatus, copy to polymarket-alerts)

- `scripts/retention_alerts_log.py` – trim old rows from alerts_log.csv
- `scripts/backfill_resolved_ts.py` – backfill resolved_ts from ts
- `scripts/log_run_stats.py` – append per-run stats to run_stats.csv for trend charts

## Paths

- MiniStatus: `~/MiniStatus-MVP` (or `/home/ubuntu/MiniStatus-MVP`) on VM
- polymarket-alerts: `~/polymarket-alerts` on VM
- `.env`: `POLYMARKET_DATA_PATH=/home/ubuntu/polymarket-alerts`

## Cursor Rules

- `.cursor/rules/deploy-after-changes.mdc` – restart ministatus after edits (workspace on VM)
