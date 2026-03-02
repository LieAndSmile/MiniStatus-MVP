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

# mtime cache: filepath -> (mtime, fieldnames, rows). Invalidates when file changes.
_CSV_CACHE: dict[str, tuple[float, list[str], list[dict]]] = {}


def _read_csv_cached(filepath: str) -> Optional[tuple[list[str], list[dict]]]:
    """
    Read CSV with mtime caching. Returns (fieldnames, rows) or None.
    Cache invalidates automatically when file mtime changes.
    """
    if not filepath or not os.path.isfile(filepath):
        return None
    try:
        mtime = os.path.getmtime(filepath)
    except OSError:
        return None
    if filepath in _CSV_CACHE:
        cached_mtime, cached_fieldnames, cached_rows = _CSV_CACHE[filepath]
        if cached_mtime == mtime:
            return (cached_fieldnames, cached_rows)
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        _CSV_CACHE[filepath] = (mtime, fieldnames, rows)
        return (fieldnames, rows)
    except (IOError, csv.Error):
        return None


def format_compact_usd(val: float) -> str:
    """Format USD with compact notation for large amounts (e.g. $266.5K, $1.2M)."""
    if val >= 1_000_000:
        return f"${val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"${val / 1_000:.1f}K"
    return f"${val:.2f}"


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


# Required columns for alerts_log.csv schema validation
ALERTS_LOG_REQUIRED = ("question", "pnl_usd", "resolved", "actual_result")
ALERTS_LOG_NEEDS_ONE_OF = ("ts", "resolved_ts")

# Empty stats structure for error/fallback responses
_STATS_EMPTY = {
    "alerts_total": 0,
    "resolved": 0,
    "wins": 0,
    "losses": 0,
    "total_pnl": 0.0,
    "total_pnl_display": "$0.00",
    "resolved_list": [],
    "chart_data": [],
    "max_drawdown": 0,
    "max_drawdown_display": "$0.00",
    "worst_period": "",
}


def build_pagination(total_count: int, page: int, per_page: int) -> dict:
    """Build pagination dict for template context."""
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)
    start = (page - 1) * per_page
    return {
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "total_count": total_count,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "start": start + 1 if total_count else 0,
        "end": min(start + per_page, total_count),
    }


def validate_alerts_log_schema(data_path: str) -> tuple[bool, Optional[str]]:
    """
    Validate alerts_log.csv schema. Returns (is_valid, error_message).
    Checks: required headers exist, pnl_usd parses, timestamps parse.
    Uses cached read when available.
    """
    if not data_path or not os.path.isdir(data_path):
        return True, None  # No path = not configured, skip validation

    csv_path = os.path.join(data_path, "alerts_log.csv")
    if not os.path.isfile(csv_path):
        return True, None  # No file yet = OK

    try:
        result = _read_csv_cached(csv_path)
        if result is None:
            return False, "Could not read CSV"
        fieldnames, rows = result
        headers = [h.strip() for h in fieldnames if h]
        headers_lower = [h.lower() for h in headers]

        # Check required columns
        missing = [c for c in ALERTS_LOG_REQUIRED if c.lower() not in headers_lower]
        if missing:
            return False, f"Missing required columns: {', '.join(missing)}"

        # Need at least one timestamp column
        has_ts = any(c.lower() in headers_lower for c in ALERTS_LOG_NEEDS_ONE_OF)
        if not has_ts:
            return False, "Missing timestamp column (need 'ts' or 'resolved_ts')"

        # Sample first 50 rows: pnl_usd must parse where present
        pnl_failures = 0
        for i, row in enumerate(rows[:50]):
            pnl_val = row.get("pnl_usd", "")
            if pnl_val and str(pnl_val).strip():
                try:
                    float(str(pnl_val).strip())
                except (ValueError, TypeError):
                    pnl_failures += 1
                    if pnl_failures > 3:
                        return False, f"pnl_usd parse errors (expected numeric values, got e.g. {repr(pnl_val)[:50]})"

        return True, None
    except (IOError, csv.Error) as e:
        return False, f"Could not read CSV: {e}"


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
    category: Optional[str] = None,
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

    valid, schema_error = validate_alerts_log_schema(data_path)
    if not valid:
        return {**_STATS_EMPTY, "error": f"CSV schema mismatch: {schema_error}"}

    resolved_rows = []
    alerts_total = 0

    try:
        result = _read_csv_cached(csv_path)
        if result is None:
            return {**_STATS_EMPTY, "error": "Could not read CSV"}
        fieldnames, all_rows = result
        if not fieldnames:
            return _STATS_EMPTY.copy()

        for row in all_rows:
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

                cat = _categorize_question(question)
                resolved_rows.append({
                    "question": label,
                    "category": cat,
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
        return {**_STATS_EMPTY, "error": str(e)}

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

    # Filter by category (e.g. from Loss Lab drill-down)
    if category and category.strip():
        category_lower = category.strip().lower()
        resolved_rows = [r for r in resolved_rows if (r.get("category") or "").lower() == category_lower]

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

    wins = sum(1 for r in resolved_rows if r["pnl_usd"] > 0)
    losses = sum(1 for r in resolved_rows if r["pnl_usd"] < 0)
    total_pnl = sum(r["pnl_usd"] for r in resolved_rows)

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
    peak = 0.0
    max_drawdown = 0.0
    worst_start = ""
    worst_end = ""
    chart_data = []
    for r in chart_rows:
        cumulative += r["pnl_usd"]
        peak = max(peak, cumulative)
        dd = cumulative - peak
        if dd < max_drawdown:
            max_drawdown = dd
            worst_end = r["resolved_ts"].strftime("%Y-%m-%d")
        chart_data.append({
            "date": r["resolved_ts"].strftime("%Y-%m-%d"),
            "pnl": round(cumulative, 2),
            "drawdown": round(dd, 2),
        })
    # Find worst period start (first date where we were at peak before drawdown)
    if chart_data and max_drawdown < 0:
        peak_at = 0.0
        for d in chart_data:
            if d["pnl"] >= peak_at:
                peak_at = d["pnl"]
                worst_start = d["date"]

    return {
        "alerts_total": alerts_total,
        "resolved": len(resolved_rows),
        "wins": wins,
        "losses": losses,
        "total_pnl": round(total_pnl, 2),
        "total_pnl_display": f"${total_pnl:.2f}",
        "resolved_list": sorted_rows,
        "chart_data": chart_data,
        "max_drawdown": round(max_drawdown, 2),
        "max_drawdown_display": f"${max_drawdown:.2f}",
        "worst_period": f"{worst_start} → {worst_end}" if worst_start and worst_end else "",
    }


def is_polymarket_configured() -> bool:
    """Check if Polymarket integration is configured and data path exists."""
    path = os.getenv("POLYMARKET_DATA_PATH", "").strip()
    return bool(path and os.path.isdir(path))


def get_open_positions(data_path: str) -> list[dict]:
    """
    Read open_positions.csv from polymarket-alerts directory.
    Returns list of dicts: market_id, question, side, shares, avg_price, cost_usd,
    current_mid, unrealized_pnl, last_updated.
    """
    if not data_path or not os.path.isdir(data_path):
        return []

    csv_path = os.path.join(data_path, "open_positions.csv")
    if not os.path.isfile(csv_path):
        return []

    result = _read_csv_cached(csv_path)
    if result is None:
        return []
    _, raw_rows = result
    rows = []
    try:
        for row in raw_rows:
            cost = _parse_float(row.get("cost_usd", 0))
            unrealized = _parse_float(row.get("unrealized_pnl", 0))
            link = (row.get("link") or "").strip()
            rows.append({
                "market_id": (row.get("market_id") or "").strip(),
                "question": (row.get("question") or "").strip()[:200],
                "side": (row.get("side") or "YES").strip(),
                "shares": _parse_float(row.get("shares", 0)),
                "avg_price": _parse_float(row.get("avg_price", 0)),
                "cost_usd": cost,
                "current_mid": _parse_float(row.get("current_mid", 0)),
                "unrealized_pnl": unrealized,
                "unrealized_display": "—" if unrealized == 0 else f"${unrealized:.2f}",
                "cost_display": format_compact_usd(cost),
                "last_updated": (row.get("last_updated") or "").strip(),
                "link": link if link.startswith("http") else "",
            })
    except (IOError, csv.Error):
        return []
    return rows


def get_exposure_summary(positions: list[dict]) -> list[dict]:
    """
    Group open positions by category (politics, sports, crypto, etc.).
    Returns list of dicts: category, cost_usd, unrealized_pnl, count, positions (top examples).
    """
    from collections import defaultdict
    by_cat = defaultdict(lambda: {"cost": 0.0, "unrealized": 0.0, "positions": []})
    for p in positions:
        cat = _categorize_question(p.get("question", ""))
        by_cat[cat]["cost"] += p.get("cost_usd", 0)
        by_cat[cat]["unrealized"] += p.get("unrealized_pnl", 0)
        by_cat[cat]["positions"].append(p)
    result = []
    for cat, data in sorted(by_cat.items(), key=lambda x: -x[1]["cost"]):
        result.append({
            "category": cat.upper(),
            "cost_usd": round(data["cost"], 2),
            "cost_display": format_compact_usd(data["cost"]),
            "unrealized_pnl": round(data["unrealized"], 2),
            "unrealized_display": "—" if data["unrealized"] == 0 else f"${data['unrealized']:.2f}",
            "count": len(data["positions"]),
            "top_positions": sorted(data["positions"], key=lambda x: -x.get("cost_usd", 0))[:5],
        })
    return result


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

    result = _read_csv_cached(stats_path)
    if result is None:
        return []
    fieldnames, raw_rows = result
    if not fieldnames:
        return []

    rows = []
    try:
        for row in raw_rows:
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


# Edge bands (as decimal): 0-0.5%, 0.5-1%, 1-2%, 2%+
_EDGE_BANDS = [(0, 0.005, "0–0.5%"), (0.005, 0.01, "0.5–1%"), (0.01, 0.02, "1–2%"), (0.02, 1.0, "2%+")]
# Gamma bands: 0.90-0.92, 0.92-0.94, 0.94-0.96, 0.96-0.98, 0.98-1.0
_GAMMA_BANDS = [(0.90, 0.92), (0.92, 0.94), (0.94, 0.96), (0.96, 0.98), (0.98, 1.01)]


def get_expectancy_by_bands(data_path: str, days: Optional[int] = None) -> dict:
    """
    Compute expectancy by edge and gamma bands from resolved alerts.
    Returns { "edge_bands": [...], "gamma_bands": [...] }.
    Each band: label, count, wins, win_rate, total_pnl, avg_pnl, expectancy.
    """
    if not data_path or not os.path.isdir(data_path):
        return {"edge_bands": [], "gamma_bands": []}

    csv_path = os.path.join(data_path, "alerts_log.csv")
    if not os.path.isfile(csv_path):
        return {"edge_bands": [], "gamma_bands": []}

    valid, _ = validate_alerts_log_schema(data_path)
    if not valid:
        return {"edge_bands": [], "gamma_bands": []}

    result = _read_csv_cached(csv_path)
    if result is None:
        return {"edge_bands": [], "gamma_bands": []}
    _, raw_rows = result

    resolved = []
    try:
        for row in raw_rows:
            if not _parse_bool(row.get("resolved", "")) and (row.get("actual_result") or "").strip().upper() not in ("YES", "NO"):
                continue
            pnl = _parse_float(row.get("pnl_usd", 0))
            edge = _parse_float(row.get("edge", 0))
            gamma = _parse_float(row.get("gamma", 0))
            resolved_ts = _parse_date(row.get("resolved_ts") or row.get("ts"))
            resolved.append({"pnl": pnl, "edge": edge, "gamma": gamma, "resolved_ts": resolved_ts})
    except (IOError, csv.Error):
        return {"edge_bands": [], "gamma_bands": []}

    if days and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        resolved = [r for r in resolved if r["resolved_ts"] and (r["resolved_ts"].replace(tzinfo=timezone.utc) if r["resolved_ts"].tzinfo is None else r["resolved_ts"]) >= cutoff]

    edge_result = []
    for lo, hi, lbl in _EDGE_BANDS:
        rows = [r for r in resolved if lo <= r["edge"] < hi]
        n = len(rows)
        wins = sum(1 for r in rows if r["pnl"] > 0)
        total = sum(r["pnl"] for r in rows)
        avg = total / n if n else 0
        edge_result.append({"label": lbl, "count": n, "wins": wins, "win_rate": round((wins / n * 100) if n else 0, 1), "total_pnl": round(total, 2), "avg_pnl": round(avg, 2), "expectancy": round(avg, 2)})

    gamma_result = []
    for lo, hi in _GAMMA_BANDS:
        rows = [r for r in resolved if lo <= r["gamma"] < hi]
        n = len(rows)
        wins = sum(1 for r in rows if r["pnl"] > 0)
        total = sum(r["pnl"] for r in rows)
        avg = total / n if n else 0
        gamma_result.append({"label": f"{lo:.2f}–{hi:.2f}", "count": n, "wins": wins, "win_rate": round((wins / n * 100) if n else 0, 1), "total_pnl": round(total, 2), "avg_pnl": round(avg, 2), "expectancy": round(avg, 2)})

    # Filter out empty bands (count == 0)
    edge_filtered = [b for b in edge_result if b["count"] > 0]
    gamma_filtered = [b for b in gamma_result if b["count"] > 0]

    # Best band by expectancy (for insight line)
    insight_edge = max(edge_filtered, key=lambda b: b["expectancy"]) if edge_filtered else None
    insight_gamma = max(gamma_filtered, key=lambda b: b["expectancy"]) if gamma_filtered else None

    return {
        "edge_bands": edge_filtered,
        "gamma_bands": gamma_filtered,
        "insight_edge": insight_edge,
        "insight_gamma": insight_gamma,
    }


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

    result = _read_csv_cached(csv_path)
    if result is None:
        return []
    _, raw_rows = result

    try:
        for row in raw_rows:
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

    result = _read_csv_cached(csv_path)
    if result is None:
        return None
    _, raw_rows = result

    rows = []
    try:
        for row in raw_rows:
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
