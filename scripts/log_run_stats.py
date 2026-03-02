#!/usr/bin/env python3
"""
Append per-run stats to run_stats.csv for trend analysis.

Each run appends one row: ts, resolved, wins, losses, total_pnl, alerts_total.
MiniStatus reads this file to show trend charts (resolved count, P/L over time).

Usage:
  # From polymarket-alerts directory (default: ./alerts_log.csv, writes ./run_stats.csv)
  python log_run_stats.py

  # With explicit path
  python log_run_stats.py --csv /home/ubuntu/polymarket-alerts/alerts_log.csv

  # Dry run (print stats, don't append)
  python log_run_stats.py --dry-run

Run after resolution_tracker.py (e.g. in same cron/timer or as a chained step).
Copy this script to polymarket-alerts.
"""
import argparse
import csv
import os
from datetime import datetime, timezone


def parse_float(val, default=0.0):
    if val is None or val == "":
        return default
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default


def parse_bool(val):
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ("true", "1", "yes")


def main():
    parser = argparse.ArgumentParser(description="Append per-run stats for trend analysis")
    parser.add_argument("--csv", default="alerts_log.csv", help="Path to alerts_log.csv")
    parser.add_argument("--dry-run", action="store_true", help="Print stats, don't append to run_stats.csv")
    args = parser.parse_args()

    csv_path = os.path.abspath(args.csv)
    if not os.path.isfile(csv_path):
        print(f"Error: {csv_path} not found")
        return 1

    data_dir = os.path.dirname(csv_path)
    stats_path = os.path.join(data_dir, "run_stats.csv")
    fieldnames = ["ts", "resolved", "wins", "losses", "total_pnl", "alerts_total"]

    resolved = 0
    wins = 0
    losses = 0
    total_pnl = 0.0
    alerts_total = 0

    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                alerts_total += 1
                resolved_val = row.get("resolved", "")
                actual_result = (row.get("actual_result") or "").strip().upper()
                is_resolved = parse_bool(resolved_val) or actual_result in ("YES", "NO")
                if not is_resolved:
                    continue

                resolved += 1
                pnl = parse_float(row.get("pnl_usd", ""))
                total_pnl += pnl
                if pnl > 0:
                    wins += 1
                elif pnl < 0:
                    losses += 1
    except (IOError, csv.Error) as e:
        print(f"Error reading {csv_path}: {e}")
        return 1

    row = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "resolved": resolved,
        "wins": wins,
        "losses": losses,
        "total_pnl": round(total_pnl, 2),
        "alerts_total": alerts_total,
    }

    if args.dry_run:
        print(f"Would append: {row}")
        return 0

    write_header = not os.path.isfile(stats_path)
    try:
        with open(stats_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
    except (IOError, csv.Error) as e:
        print(f"Error writing {stats_path}: {e}")
        return 1

    print(f"Appended run stats: resolved={resolved}, wins={wins}, losses={losses}, pnl=${total_pnl:.2f}")
    return 0


if __name__ == "__main__":
    exit(main())
