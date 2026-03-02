#!/usr/bin/env python3
"""
Analyze lost bets by market category (politics, sports, crypto, etc.).

Usage:
  python analyze_losses_by_category.py [--csv path/to/alerts_log.csv]
  # Or from polymarket-alerts dir: python analyze_losses_by_category.py

Output: breakdown of losses by category with count and total P/L.
"""
import argparse
import csv
import os
import re
from collections import defaultdict


# Keywords to categorize markets (case-insensitive)
CATEGORIES = {
    "politics": [
        "trump", "biden", "election", "congress", "senate", "president", "governor",
        "vote", "iran", "israel", "ukraine", "russia", "putin", "zelensky",
        "democrat", "republican", "primary", "nominee", "cabinet", "impeach",
    ],
    "sports": [
        "fc", " vs ", "o/u", "over", "under", "nfl", "nba", "mlb", "nhl",
        "soccer", "football", "basketball", "baseball", "hockey", "spread",
        "mariners", "jets", "wolves", "united", "wanderers", "wolverhampton",
    ],
    "crypto": [
        "bitcoin", "btc", "eth", "ethereum", "solana", "sol ", "crypto",
        "cryptocurrency", "defi", "nft",
    ],
    "entertainment": [
        "oscar", "grammy", "emmy", "award", "movie", "film", "album",
    ],
}


def categorize(question: str) -> str:
    """Return category for a question, or 'other' if no match."""
    if not question or not isinstance(question, str):
        return "other"
    q = question.lower()
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in q:
                return cat
    return "other"


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
    parser = argparse.ArgumentParser(description="Analyze losses by market category")
    parser.add_argument("--csv", default="alerts_log.csv", help="Path to alerts_log.csv")
    args = parser.parse_args()

    csv_path = os.path.abspath(args.csv)
    if not os.path.isfile(csv_path):
        # Try POLYMARKET_DATA_PATH
        data_path = os.getenv("POLYMARKET_DATA_PATH", "").strip()
        if data_path:
            csv_path = os.path.join(data_path, "alerts_log.csv")
        if not os.path.isfile(csv_path):
            print(f"Error: {args.csv} not found")
            return 1

    losses_by_cat = defaultdict(lambda: {"count": 0, "pnl": 0.0, "questions": []})

    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                resolved_val = row.get("resolved", "")
                actual_result = (row.get("actual_result") or "").strip().upper()
                is_resolved = parse_bool(resolved_val) or actual_result in ("YES", "NO")
                if not is_resolved:
                    continue

                pnl = parse_float(row.get("pnl_usd", ""))
                if pnl >= 0:
                    continue

                question = (row.get("question") or "").strip()
                cat = categorize(question)
                losses_by_cat[cat]["count"] += 1
                losses_by_cat[cat]["pnl"] += pnl
                losses_by_cat[cat]["questions"].append((question[:60], pnl))
    except (IOError, csv.Error) as e:
        print(f"Error: {e}")
        return 1

    # Sort by total loss (most negative first)
    sorted_cats = sorted(
        losses_by_cat.items(),
        key=lambda x: x[1]["pnl"],
    )

    print("\n=== Losses by category ===\n")
    total_losses = 0
    total_pnl = 0.0
    for cat, data in sorted_cats:
        count = data["count"]
        pnl = data["pnl"]
        total_losses += count
        total_pnl += pnl
        print(f"{cat.upper()}: {count} losses, ${pnl:.2f} total")
        for q, p in data["questions"][:3]:  # Show up to 3 examples
            print(f"  - {q}... (${p:.2f})")
        if len(data["questions"]) > 3:
            print(f"  ... and {len(data['questions']) - 3} more")
        print()

    print(f"TOTAL: {total_losses} losses, ${total_pnl:.2f}")
    return 0


if __name__ == "__main__":
    exit(main())
