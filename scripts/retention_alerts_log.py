#!/usr/bin/env python3
"""
Trim alerts_log.csv to keep only rows from the last N days.

Usage:
  # From polymarket-alerts directory (default: ./alerts_log.csv)
  python retention_alerts_log.py --days 90

  # With explicit path
  python retention_alerts_log.py --csv /home/ubuntu/polymarket-alerts/alerts_log.csv --days 90

  # Dry run (show what would be removed, don't modify)
  python retention_alerts_log.py --days 90 --dry-run

Copy this script to polymarket-alerts and run via cron, e.g.:
  0 3 * * 0 cd /home/ubuntu/polymarket-alerts && python retention_alerts_log.py --days 90
"""
import argparse
import csv
import os
import shutil
from datetime import datetime, timedelta, timezone


def parse_date(val):
    """Parse date from ts or resolved_ts."""
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    if not val:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            s = val[:19] if len(val) >= 10 else val
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description="Trim alerts_log.csv by retention days")
    parser.add_argument("--csv", default="alerts_log.csv", help="Path to alerts_log.csv")
    parser.add_argument("--days", type=int, default=90, help="Keep rows from last N days (default: 90)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed, don't modify")
    args = parser.parse_args()

    csv_path = os.path.abspath(args.csv)
    if not os.path.isfile(csv_path):
        print(f"Error: {csv_path} not found")
        return 1

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    kept = []
    removed = 0

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            print("Error: empty or invalid CSV")
            return 1

        for row in reader:
            ts = parse_date(row.get("resolved_ts") or row.get("ts"))
            if ts is None:
                kept.append(row)
                continue
            ts_aware = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
            if ts_aware >= cutoff:
                kept.append(row)
            else:
                removed += 1

    total_before = len(kept) + removed
    print(f"Total rows: {total_before}")
    print(f"Keeping: {len(kept)} (last {args.days} days)")
    print(f"Removing: {removed}")

    if args.dry_run:
        print("(dry run - no changes made)")
        return 0

    if removed == 0:
        print("Nothing to remove.")
        return 0

    backup_path = csv_path + ".bak"
    shutil.copy2(csv_path, backup_path)
    print(f"Backup: {backup_path}")

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"Done. Trimmed {removed} rows.")
    return 0


if __name__ == "__main__":
    exit(main())
