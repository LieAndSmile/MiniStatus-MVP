#!/usr/bin/env python3
"""
Backfill missing resolved_ts in alerts_log.csv from ts column.

Resolved rows without resolved_ts won't appear in date filters or the P/L chart.
This script copies ts -> resolved_ts for resolved rows that lack it.

Usage:
  python backfill_resolved_ts.py [--csv path/to/alerts_log.csv] [--dry-run]
"""
import argparse
import csv
import os
import shutil


def main():
    parser = argparse.ArgumentParser(description="Backfill resolved_ts from ts for resolved rows")
    parser.add_argument("--csv", default="alerts_log.csv", help="Path to alerts_log.csv")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed, don't modify")
    args = parser.parse_args()

    csv_path = os.path.abspath(args.csv)
    if not os.path.isfile(csv_path):
        print(f"Error: {csv_path} not found")
        return 1

    rows = []
    fieldnames = None
    backfilled = 0

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            print("Error: empty or invalid CSV")
            return 1

        if "resolved_ts" not in fieldnames:
            fieldnames = list(fieldnames) + ["resolved_ts"]

        for row in reader:
            resolved_val = (row.get("resolved") or "").strip().lower()
            actual_result = (row.get("actual_result") or "").strip().upper()
            resolved_ts = (row.get("resolved_ts") or "").strip()
            ts = (row.get("ts") or "").strip()

            is_resolved = resolved_val in ("true", "1", "yes") or actual_result in ("YES", "NO")
            needs_backfill = is_resolved and not resolved_ts and ts

            if needs_backfill:
                row["resolved_ts"] = ts
                backfilled += 1
            elif "resolved_ts" not in row:
                row["resolved_ts"] = resolved_ts or ""

            rows.append(row)

    print(f"Rows needing backfill: {backfilled}")

    if args.dry_run:
        print("(dry run - no changes made)")
        return 0

    if backfilled == 0:
        print("Nothing to backfill.")
        return 0

    backup_path = csv_path + ".bak"
    shutil.copy2(csv_path, backup_path)
    print(f"Backup: {backup_path}")

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. Backfilled {backfilled} rows.")
    return 0


if __name__ == "__main__":
    exit(main())
