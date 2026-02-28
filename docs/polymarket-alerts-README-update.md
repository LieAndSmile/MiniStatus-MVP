# Polymarket Alerts

Telegram alerts for high-edge Polymarket markets. Fetches active markets, filters by gamma, depth, spread, and edge, then sends alerts and a summary to Telegram. Optionally track resolutions and P/L via `resolution_tracker.py`.

## Setup

1. **Clone or copy** this folder to the server (e.g. `/root/polymarket-alerts`).

2. **Create virtualenv and install dependencies:**
   ```bash
   cd /root/polymarket-alerts
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ```

3. **Configure `.env`:**
   ```bash
   cp .env.example .env
   # Edit .env: set TELEGRAM_TOKEN and CHAT_ID (required).
   # Optionally override thresholds (see .env.example).
   ```

## Run

- **Manual (foreground):**
  ```bash
  cd /root/polymarket-alerts
  ./venv/bin/python pm_alerts.py
  ```
  Alerts run in a loop (e.g. every 6 hours). Use Ctrl+C to stop.

- **As systemd service (recommended):**
  ```bash
  sudo systemctl enable polymarket-alerts
  sudo systemctl start polymarket-alerts
  sudo systemctl status polymarket-alerts
  ```

- **Resolution tracker** (check resolved markets and P/L):
  - Manual once: `./venv/bin/python resolution_tracker.py --once`
  - On a schedule: enable the timer: `sudo systemctl enable polymarket-resolution-tracker.timer && sudo systemctl start polymarket-resolution-tracker.timer`

## MiniStatus Integration

When running on the same machine as [MiniStatus](https://github.com/LieAndSmile/MiniStatus-MVP), you can configure MiniStatus to read polymarket-alerts data for an admin dashboard:

1. Set `POLYMARKET_DATA_PATH` in MiniStatus's `.env` to this directory (e.g. `/home/ubuntu/polymarket-alerts`).
2. Log in to MiniStatus admin and open **Polymarket** in the sidebar.

MiniStatus reads:
- `alerts_log.csv` – resolved stats, wins/losses, filters, export
- `polymarket_alerts.log` – last run time ("X hours ago")

No changes to polymarket-alerts are required; MiniStatus reads the files directly.

## Retention Script

To trim old rows from `alerts_log.csv` (e.g. keep last 90 days), use the retention script. Copy it from MiniStatus:

```bash
cp /path/to/MiniStatus-MVP/scripts/retention_alerts_log.py .
python3 retention_alerts_log.py --days 90 --dry-run   # Preview
python3 retention_alerts_log.py --days 90             # Trim (creates .bak backup)
```

Optional cron (weekly on Sunday at 3 AM):

```bash
0 3 * * 0 cd /home/ubuntu/polymarket-alerts && python3 retention_alerts_log.py --days 90
```

## Module layout (pm_alerts)

The alert pipeline is split into modules for easier testing and changes:

| Module | Role 
|--------|-----
| `config.py` | Env-based thresholds and constants (GAMMA_MIN, BEST_ASK_*, paths, etc.). 
| `api.py` | Gamma/CLOB: `fetch_markets`, `get_best_ask` / `get_best_bid`, `get_orderbook`, `simulate_buy_500`, `get_trade_link`. 
| `filters.py` | Filter logic: `filter_market_*`, `filter_outcome_*`, `filter_alert_effective_edge` (return rejection key or None). 
| `telegram_utils.py` | `send_telegram(message)`. 
| `main_loop.py` | One scan: load cooldown, `init_csvs`, run loop (api + filters), write CSVs, send summary. 
| `pm_alerts.py` | Entry point: logging, `init_csvs`, then `while True: main_loop.main_loop(); sleep`. 


## Files

| File | Purpose |
|------|--------|
| `pm_alerts.py` | Main script: fetch markets, filter, send Telegram alerts. |
| `resolution_tracker.py` | Reads `alerts_log.csv`, checks resolutions, updates P/L, sends summary. |
| `retention_alerts_log.py` | Optional: trim old rows from alerts_log.csv (copy from MiniStatus). |
| `.env` | Config: `TELEGRAM_TOKEN`, `CHAT_ID`, and optional thresholds. |
| `alerts_log.csv` | Log of every alert sent (used by resolution_tracker and MiniStatus). |
| `cooldown.json` | Per-token cooldown so the same market isn't re-alerted. |
| `polymarket_alerts.log` | Application log (used by MiniStatus for "last run"; rotate with logrotate). |
| `venv/` | Python virtual environment. |

## Logs

- Application log: `polymarket_alerts.log` (in project dir). Rotate with logrotate (e.g. `/etc/logrotate.d/polymarket-alerts`).
- If run via systemd: `journalctl -u polymarket-alerts -f`
