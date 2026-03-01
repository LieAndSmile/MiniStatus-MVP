"""
Polymarket Alerts integration - reads CSV data from polymarket-alerts directory.
"""
import csv
import os
import re
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal


def _parse_float(val, default: float = 0.0) -> float:
    """Safely parse float from CSV value."""
    if val is None or val == "":
        return default
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default


def _parse_bool(val) -> bool:
    """Parse resolved flag."""
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ("true", "1", "yes")


def _get_display_label(question: str, max_len: int = 80) -> str:
    """Get a display-safe label, truncating and cleaning malformed data."""
    if not question or not isinstance(question, str):
        return "(unknown)"
    # Skip if it looks like a token ID or numeric junk
    q = question.strip()
    if q.isdigit() or (len(q) > 20 and q.replace(".", "").replace("-", "").isdigit()):
        return "(unknown)"
    if len(q) > max_len:
        return q[: max_len - 3] + "..."
    return q


def _parse_date(val) -> Optional[datetime]:
    """Parse date from ts or resolved_ts column for retention filtering."""
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    if not val:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(val[:19], fmt) if len(val) >= 10 else datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


SORT_OPTIONS = (
    "pnl_asc",      # P/L lowest first (biggest losses first)
    "pnl_desc",     # P/L highest first (biggest wins first)
    "date_desc",    # Newest first
    "date_asc",     # Oldest first
    "question_asc", # Question A–Z
    "question_desc",# Question Z–A
    "result_yes",   # YES first
    "result_no",    # NO first
)


def get_polymarket_stats(
    data_path: str,
    filter: Literal["all", "wins", "losses"] = "all",
    days: Optional[int] = None,
    sort: str = "pnl_asc",
) -> Optional[dict]:
    """
    Read alerts_log.csv from polymarket-alerts directory and compute stats.
    Returns dict with: alerts_total, resolved, wins, losses, total_pnl, resolved_list.
    filter: "all" | "wins" | "losses" - filter displayed list
    days: if set, only include resolved alerts older than (now - days) days
    sort: pnl_asc | pnl_desc | date_desc | date_asc | question_asc | question_desc | result_yes | result_no
    """
    if not data_path or not os.path.isdir(data_path):
        return None

    csv_path = os.path.join(data_path, "alerts_log.csv")
    if not os.path.isfile(csv_path):
        return None

    resolved_rows = []
    alerts_total = 0

    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return {"alerts_total": 0, "resolved": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "resolved_list": [], "chart_data": []}

            for row in reader:
                alerts_total += 1
                resolved_val = row.get("resolved", "")
                actual_result = (row.get("actual_result") or "").strip().upper()
                pnl_str = row.get("pnl_usd", "")

                is_resolved = _parse_bool(resolved_val) or actual_result in ("YES", "NO")
                if not is_resolved:
                    continue

                pnl = _parse_float(pnl_str)
                question = row.get("question", "")
                link = (row.get("link") or "").strip()
                label = _get_display_label(question)

                # Parse date for retention filter (resolved_ts preferred, fallback to ts)
                resolved_ts = _parse_date(row.get("resolved_ts") or row.get("ts"))

                gamma = _parse_float(row.get("gamma"))
                best_ask = _parse_float(row.get("best_ask"))
                effective = _parse_float(row.get("effective"))
                fill_pct = _parse_float(row.get("fill_pct"))
                edge = _parse_float(row.get("edge"))
                spread = _parse_float(row.get("spread"))

                resolved_rows.append({
                    "question": label,
                    "actual_result": actual_result or "—",
                    "pnl_usd": pnl,
                    "link": link if link.startswith("http") else "",
                    "resolved_ts": resolved_ts,
                    "rationale": {
                        "gamma": gamma,
                        "best_ask": best_ask,
                        "effective": effective,
                        "fill_pct": fill_pct,
                        "edge": edge,
                        "spread": spread,
                    },
                })
    except (IOError, csv.Error) as e:
        return {"error": str(e), "alerts_total": 0, "resolved": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "resolved_list": [], "chart_data": []}

    # Retention filter: exclude resolved older than (now - days)
    if days is not None and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        def _within_cutoff(r):
            ts = r.get("resolved_ts")
            if not ts:
                return True  # no date = keep
            ts_aware = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
            return ts_aware >= cutoff
        resolved_rows = [r for r in resolved_rows if _within_cutoff(r)]

    wins = sum(1 for r in resolved_rows if r["pnl_usd"] > 0)
    losses = sum(1 for r in resolved_rows if r["pnl_usd"] < 0)
    total_pnl = sum(r["pnl_usd"] for r in resolved_rows)

    # Chart data: cumulative P/L over time (before wins/losses filter)
    chart_rows = sorted(
        [r for r in resolved_rows if r.get("resolved_ts")],
        key=lambda x: x["resolved_ts"],
    )

    # Filter by wins/losses
    if filter == "wins":
        resolved_rows = [r for r in resolved_rows if r["pnl_usd"] > 0]
    elif filter == "losses":
        resolved_rows = [r for r in resolved_rows if r["pnl_usd"] < 0]

    # Sort
    if sort not in SORT_OPTIONS:
        sort = "pnl_asc"
    _ts = lambda x: (x["resolved_ts"] or datetime.min).timestamp()
    if sort == "pnl_asc":
        sorted_rows = sorted(resolved_rows, key=lambda x: (x["pnl_usd"], -_ts(x)))
    elif sort == "pnl_desc":
        sorted_rows = sorted(resolved_rows, key=lambda x: (-x["pnl_usd"], -_ts(x)))
    elif sort == "date_desc":
        sorted_rows = sorted(resolved_rows, key=lambda x: (-_ts(x), x["pnl_usd"]))
    elif sort == "date_asc":
        sorted_rows = sorted(resolved_rows, key=lambda x: (_ts(x), x["pnl_usd"]))
    elif sort == "question_asc":
        sorted_rows = sorted(resolved_rows, key=lambda x: ((x.get("question") or "").lower(), -_ts(x)))
    elif sort == "question_desc":
        sorted_rows = sorted(resolved_rows, key=lambda x: ((x.get("question") or "").lower(), -_ts(x)), reverse=True)
    elif sort == "result_yes":
        sorted_rows = sorted(resolved_rows, key=lambda x: (x.get("actual_result") != "YES", -_ts(x)))
    elif sort == "result_no":
        sorted_rows = sorted(resolved_rows, key=lambda x: (x.get("actual_result") != "NO", -_ts(x)))
    else:
        sorted_rows = sorted(resolved_rows, key=lambda x: (x["pnl_usd"], -_ts(x)))

    for r in sorted_rows:
        r["pnl_display"] = f"${r['pnl_usd']:.2f}"
    cumulative = 0.0
    chart_data = []
    for r in chart_rows:
        cumulative += r["pnl_usd"]
        chart_data.append({
            "date": r["resolved_ts"].strftime("%Y-%m-%d"),
            "pnl": round(cumulative, 2),
        })

    return {
        "alerts_total": alerts_total,
        "resolved": len(resolved_rows),
        "wins": wins,
        "losses": losses,
        "total_pnl": round(total_pnl, 2),
        "total_pnl_display": f"${total_pnl:.2f}",
        "resolved_list": sorted_rows,
        "chart_data": chart_data,
    }


def is_polymarket_configured() -> bool:
    """Check if Polymarket integration is configured and data path exists."""
    path = os.getenv("POLYMARKET_DATA_PATH", "").strip()
    return bool(path and os.path.isdir(path))


def get_run_stats_log(data_path: str, limit: int = 365) -> list[dict]:
    """
    Read run_stats.csv (per-run stats log) for trend analysis.
    Returns list of dicts: ts, resolved, wins, losses, total_pnl, alerts_total.
    limit: max number of rows to return (newest first).
    """
    if not data_path or not os.path.isdir(data_path):
        return []

    stats_path = os.path.join(data_path, "run_stats.csv")
    if not os.path.isfile(stats_path):
        return []

    rows = []
    try:
        with open(stats_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return []
            for row in reader:
                ts_str = row.get("ts", "").strip()
                ts = _parse_date(ts_str) if ts_str else None
                rows.append({
                    "ts": ts,
                    "ts_display": ts_str[:10] if ts_str else "",
                    "resolved": int(_parse_float(row.get("resolved", 0))),
                    "wins": int(_parse_float(row.get("wins", 0))),
                    "losses": int(_parse_float(row.get("losses", 0))),
                    "total_pnl": _parse_float(row.get("total_pnl", 0)),
                    "alerts_total": int(_parse_float(row.get("alerts_total", 0))),
                })
    except (IOError, csv.Error):
        return []

    # Newest first, then take limit
    rows.sort(key=lambda x: (x["ts"] or datetime.min).timestamp() if x["ts"] else 0, reverse=True)
    return rows[:limit]


# Keywords to categorize markets for loss breakdown (case-insensitive)
_LOSS_CATEGORIES = {
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


def _categorize_question(question: str) -> str:
    """Return category for a question, or 'other' if no match."""
    if not question or not isinstance(question, str):
        return "other"
    q = question.lower()
    for cat, keywords in _LOSS_CATEGORIES.items():
        for kw in keywords:
            if kw in q:
                return cat
    return "other"


def get_loss_breakdown(data_path: str, days: Optional[int] = None) -> list[dict]:
    """
    Analyze losses by market category (politics, sports, crypto, etc.).
    Returns list of dicts: category, count, pnl, examples (up to 3).
    Respects days filter (same as get_polymarket_stats).
    """
    if not data_path or not os.path.isdir(data_path):
        return []

    csv_path = os.path.join(data_path, "alerts_log.csv")
    if not os.path.isfile(csv_path):
        return []

    by_cat = defaultdict(lambda: {"count": 0, "pnl": 0.0, "examples": []})

    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                resolved_val = row.get("resolved", "")
                actual_result = (row.get("actual_result") or "").strip().upper()
                is_resolved = _parse_bool(resolved_val) or actual_result in ("YES", "NO")
                if not is_resolved:
                    continue

                pnl = _parse_float(row.get("pnl_usd", ""))
                if pnl >= 0:
                    continue

                question = (row.get("question") or "").strip()
                resolved_ts = _parse_date(row.get("resolved_ts") or row.get("ts"))

                # Days filter
                if days is not None and days > 0 and resolved_ts:
                    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                    ts_aware = resolved_ts.replace(tzinfo=timezone.utc) if resolved_ts.tzinfo is None else resolved_ts
                    if ts_aware < cutoff:
                        continue

                cat = _categorize_question(question)
                by_cat[cat]["count"] += 1
                by_cat[cat]["pnl"] += pnl
                if len(by_cat[cat]["examples"]) < 3:
                    by_cat[cat]["examples"].append({"question": question[:60], "pnl": pnl, "pnl_display": f"${pnl:.2f}"})
    except (IOError, csv.Error):
        return []

    result = []
    for cat, data in sorted(by_cat.items(), key=lambda x: x[1]["pnl"]):
        result.append({
            "category": cat,
            "count": data["count"],
            "pnl": round(data["pnl"], 2),
            "pnl_display": f"${data['pnl']:.2f}",
            "examples": data["examples"],
        })
    return result


DEBUG_SORT_OPTIONS = (
    "date_desc",     # Newest first
    "date_asc",      # Oldest first
    "edge_desc",     # Highest edge first
    "edge_asc",      # Lowest edge first
    "question_asc", # Question A–Z
    "question_desc",# Question Z–A
    "status",       # ALERT first, then EFFECTIVE_OUT
)


def get_debug_candidates(
    data_path: str,
    limit: int = 5000,
    status_filter: Literal["all", "alert"] = "all",
    sort: str = "date_desc",
) -> Optional[tuple[list[dict], int]]:
    """
    Read debug_candidates_v60.csv (or debug_candidates*.csv) from polymarket-alerts.
    Returns (rows, total_count). Used for Loop Summary tab.
    status_filter: "all" | "alert" – when "alert", only rows with status ALERT.
    sort: date_desc | date_asc | edge_desc | edge_asc | question_asc | question_desc | status
    """
    if not data_path or not os.path.isdir(data_path):
        return None

    # Try v60 first, then any debug_candidates*.csv
    csv_path = os.path.join(data_path, "debug_candidates_v60.csv")
    if not os.path.isfile(csv_path):
        import glob
        matches = glob.glob(os.path.join(data_path, "debug_candidates*.csv"))
        csv_path = matches[0] if matches else None
    if not csv_path or not os.path.isfile(csv_path):
        return None

    rows = []
    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                edge = _parse_float(row.get("edge"))
                ts_raw = row.get("ts", "")
                dt = _parse_date(ts_raw)
                ts_display = dt.strftime("%b %d, %Y %I:%M %p") if dt else (ts_raw[:19] if ts_raw else "—")
                question = (row.get("question") or "").strip()
                # Use link from CSV (actual event URL); fallback to search only when missing
                link = (row.get("link") or "").strip()
                if not link or not link.startswith("http"):
                    q_enc = urllib.parse.quote_plus(question.replace("?", "%3F")) if question else ""
                    link = f"https://polymarket.com/search?q={q_enc}" if q_enc else ""
                rows.append({
                    "ts": ts_raw,
                    "ts_display": ts_display,
                    "question": question[:80],
                    "link": link,
                    "gamma": _parse_float(row.get("gamma")),
                    "best_ask": _parse_float(row.get("best_ask")),
                    "spread": _parse_float(row.get("spread")),
                    "effective": _parse_float(row.get("effective")),
                    "fill_pct": _parse_float(row.get("fill_pct")),
                    "edge": edge,
                    "edge_pct": f"{edge * 100:+.2f}%" if edge else "—",
                    "days": row.get("days", ""),
                    "status": (row.get("status") or "").strip(),
                })
    except (IOError, csv.Error):
        return None

    # Status filter
    if status_filter == "alert":
        rows = [r for r in rows if (r.get("status") or "").strip().upper() == "ALERT"]

    # Sort
    def _ts_key(r):
        ts = r.get("ts", "")
        if not ts:
            return datetime.min.replace(tzinfo=timezone.utc)
        dt = _parse_date(ts)
        return dt or datetime.min.replace(tzinfo=timezone.utc)

    if sort == "date_desc":
        rows.sort(key=_ts_key, reverse=True)
    elif sort == "date_asc":
        rows.sort(key=_ts_key)
    elif sort == "edge_desc":
        rows.sort(key=lambda r: (r.get("edge") or 0, -_ts_key(r).timestamp()), reverse=True)
    elif sort == "edge_asc":
        rows.sort(key=lambda r: (r.get("edge") or 0, _ts_key(r).timestamp()))
    elif sort == "question_asc":
        rows.sort(key=lambda r: ((r.get("question") or "").lower(), -_ts_key(r).timestamp()))
    elif sort == "question_desc":
        rows.sort(key=lambda r: ((r.get("question") or "").lower(), -_ts_key(r).timestamp()), reverse=True)
    elif sort == "status":
        # ALERT first, then EFFECTIVE_OUT, then others; within each, newest first
        def _status_key(r):
            st = (r.get("status") or "").strip().upper()
            order = 0 if st == "ALERT" else (1 if st == "EFFECTIVE_OUT" else 2)
            return (order, -_ts_key(r).timestamp())
        rows.sort(key=_status_key)
    else:
        rows.sort(key=_ts_key, reverse=True)

    total = len(rows)
    return (rows[:limit], total)


def get_last_loop_time(data_path: str) -> Optional[str]:
    """
    Read polymarket_alerts.log and find the last LOOP SUMMARY timestamp.
    Returns human-readable string like "2 hours ago" or None if not found.
    """
    if not data_path or not os.path.isdir(data_path):
        return None

    log_path = os.path.join(data_path, "polymarket_alerts.log")
    if not os.path.isfile(log_path):
        return None

    last_ts = None
    # Format: 2026-02-28 08:38:14,174 | INFO | === v6.0 LOOP SUMMARY ===
    pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if "LOOP SUMMARY" in line:
                    m = pattern.match(line.strip())
                    if m:
                        try:
                            last_ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            pass
    except (IOError, OSError):
        return None

    if last_ts is None:
        return None

    now = datetime.now()
    delta = now - last_ts

    if delta.total_seconds() < 60:
        return "just now"
    if delta.total_seconds() < 3600:
        mins = int(delta.total_seconds() / 60)
        return f"{mins} min ago"
    if delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(delta.total_seconds() / 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"
