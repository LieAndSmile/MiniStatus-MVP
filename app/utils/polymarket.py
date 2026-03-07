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


# Standard date display format across Portfolio, Open Positions, Loop/Dev
TS_DISPLAY_FMT = "%Y-%m-%d %H:%M"


def format_ts_display(dt: Optional[datetime], raw_fallback: str = "") -> str:
    """Format datetime for display. Returns standard format (YYYY-MM-DD HH:MM) or fallback."""
    if dt:
        return dt.strftime(TS_DISPLAY_FMT)
    if raw_fallback:
        s = raw_fallback.replace("T", " ", 1).strip()
        return s[:16] if len(s) >= 10 else (s or "—")
    return "—"


def _parse_date(val) -> Optional[datetime]:
    """Parse date from ts or resolved_ts column for retention filtering."""
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    if not val:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(val[:19], fmt) if len(val) >= 10 else datetime.strptime(val, fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            continue
    return None


def _format_countdown(event_time: Optional[datetime]) -> str:
    """Human-readable countdown: '2d 5h', '3h 12m', 'Expired', or '—'."""
    if not event_time:
        return "—"
    now = datetime.now(timezone.utc)
    et = event_time.replace(tzinfo=timezone.utc) if event_time.tzinfo is None else event_time
    delta = et - now
    total_secs = delta.total_seconds()
    if total_secs < 0:
        return "Expired"
    if total_secs < 60:
        return "<1m"
    if total_secs < 3600:
        return f"{int(total_secs // 60)}m"
    if total_secs < 86400:
        h = int(total_secs // 3600)
        m = int((total_secs % 3600) // 60)
        return f"{h}h {m}m" if m else f"{h}h"
    d = int(total_secs // 86400)
    h = int((total_secs % 86400) // 3600)
    return f"{d}d {h}h" if h else f"{d}d"


# Required columns for alerts_log.csv schema validation
ALERTS_LOG_REQUIRED = ("question", "pnl_usd", "resolved", "actual_result")
ALERTS_LOG_NEEDS_ONE_OF = ("ts", "resolved_ts")

# v3: strategy filter options (match strategies.yaml; extended for Phase 1–3 probes)
STRATEGY_OPTIONS = (
    "safe",
    "safe_v2",
    "same_day_probe",
    "hold_3to7d_probe",
    "hold_8to10d_probe",
    "gamma_84_86_probe",
    "gamma_86_92_probe",
    "gamma_92_96_probe",
    "mid_gamma",
    "resolution_sprint",
)


def get_strategy_options_for_nav(data_path: str) -> tuple[str, ...]:
    """
    Return strategy list for nav dropdown. If analytics.json exists, merge its strategy_cohort
    keys with STRATEGY_OPTIONS so any new strategy in data appears; otherwise return STRATEGY_OPTIONS.
    """
    analytics = get_analytics_json(data_path) if data_path else None
    cohort = (analytics or {}).get("strategy_cohort") or {}
    from_data = tuple(sorted(cohort.keys())) if cohort else ()
    merged = set(STRATEGY_OPTIONS) | set(from_data)
    return tuple(sorted(merged))


def _filter_sent_rows(rows: list[dict]) -> list[dict]:
    """v3: exclude rows where status is not 'sent' (e.g. blocked_risk_limit, shadow). If no status column, keep all."""
    if not rows:
        return rows
    if "status" not in (rows[0] or {}):
        return rows
    return [r for r in rows if (r.get("status") or "").strip().lower() == "sent"]

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
    from_date: Optional[str] = None,
    sort: str = "pnl_asc",
    category: Optional[str] = None,
    strategy: Optional[str] = None,
) -> Optional[dict]:
    """
    Read alerts_log.csv from polymarket-alerts directory and compute stats.
    Returns dict with: alerts_total, resolved, wins, losses, total_pnl, resolved_list.
    filter: "all" | "wins" | "losses" - filter displayed list
    days: if set, only include resolved alerts from last N days
    from_date: if set (YYYY-MM-DD), only include resolved_ts >= that date (overrides days when both set)
    sort: pnl_asc | pnl_desc | date_desc | date_asc | question_asc | question_desc | result_yes | result_no
    strategy: if set, only include rows with strategy_id == strategy (v3).
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

        all_rows = _filter_sent_rows(all_rows)
        if strategy and strategy.strip():
            all_rows = [r for r in all_rows if (r.get("strategy_id") or "").strip() == strategy.strip()]

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

    # Date filter: from_date (YYYY-MM-DD) or days
    cutoff = None
    if from_date and len(from_date) >= 10:
        try:
            cutoff = datetime.strptime(from_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    if cutoff is None and days is not None and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    if cutoff is not None:
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
        r["resolved_ts_display"] = format_ts_display(r.get("resolved_ts"))
        r["resolved_date_param"] = r["resolved_ts"].strftime("%Y-%m-%d") if r.get("resolved_ts") else ""
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


POSITIONS_SORT_OPTIONS = (
    "cost_desc", "cost_asc", "pnl_desc", "pnl_asc",
    "gamma_desc", "gamma_asc", "edge_desc", "edge_asc",
    "expiry_asc", "expiry_desc",
    "question_asc", "question_desc", "date_desc", "date_asc",
    "interesting_first",
)

INTERESTING_POSITIONS_FILENAME = "interesting_positions.json"

POSITIONS_EXPIRY_FILTERS = ("all", "next_6h", "next_12h", "next_24h", "next_48h", "next_3d", "next_7d", "next_30d")


def get_open_positions(
    data_path: str,
    days: Optional[int] = None,
    from_date: Optional[str] = None,
    category: Optional[str] = None,
    sort: str = "cost_desc",
    expiry_filter: Optional[str] = None,
    hours_max: Optional[float] = None,
    strategy: Optional[str] = None,
) -> list[dict]:
    """
    Read open_positions.csv from polymarket-alerts directory.
    Returns list of dicts: market_id, question, side, shares, avg_price, cost_usd,
    current_mid, unrealized_pnl, last_updated, alert_ts, category, event_time, resolution_time,
    hours_remaining, countdown.
    days: if set, only include positions opened in the last N days (by alert_ts).
    from_date: if set (YYYY-MM-DD), only include alert_ts >= that date (overrides days when both set).
    category: if set, filter by category (politics, sports, crypto, other).
    sort: cost_desc, cost_asc, pnl_desc, pnl_asc, expiry_asc, expiry_desc, question_asc, question_desc, date_desc, date_asc.
    expiry_filter: all, next_6h, next_12h, next_24h, next_48h, next_3d, next_7d, next_30d - filter by hours left.
    hours_max: if set, custom max hours left (overrides expiry_filter when both set).
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
    if strategy and strategy.strip():
        raw_rows = [r for r in raw_rows if (r.get("strategy_id") or "").strip() == strategy.strip()]
    rows = []
    cutoff = None
    if from_date and len(from_date) >= 10:
        try:
            cutoff = datetime.strptime(from_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    if cutoff is None and days is not None and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        for row in raw_rows:
            cost = _parse_float(row.get("cost_usd", 0))
            unrealized = _parse_float(row.get("unrealized_pnl", 0))
            link = (row.get("link") or "").strip()
            alert_ts_raw = (row.get("alert_ts") or "").strip()
            alert_ts = _parse_date(alert_ts_raw) if alert_ts_raw else None

            if cutoff is not None:
                if alert_ts is None:
                    continue
                ts_aware = alert_ts.replace(tzinfo=timezone.utc) if alert_ts.tzinfo is None else alert_ts
                if ts_aware < cutoff:
                    continue

            question = (row.get("question") or "").strip()[:200]
            cat = _categorize_question(question)
            if category and cat.lower() != category.lower():
                continue

            gamma_val, edge_val = (row.get("gamma") or "").strip(), (row.get("edge") or "").strip()
            gamma = _parse_float(gamma_val) if gamma_val else None
            edge = _parse_float(edge_val) if edge_val else None
            alert_ts_display = format_ts_display(alert_ts, alert_ts_raw)
            alert_date_param = alert_ts.strftime("%Y-%m-%d") if alert_ts else ""
            edge_pct = f"{edge * 100:+.2f}%" if edge is not None else "—"

            event_time_raw = (row.get("event_time") or "").strip()
            event_time = _parse_date(event_time_raw) if event_time_raw else None
            now = datetime.now(timezone.utc)
            hours_remaining = (event_time - now).total_seconds() / 3600.0 if event_time else None
            resolution_time_display = format_ts_display(event_time, event_time_raw)
            countdown = _format_countdown(event_time)

            # Expiry filter by hours left
            max_hours = None
            if hours_max is not None and hours_max > 0:
                max_hours = float(hours_max)
            elif expiry_filter and expiry_filter != "all":
                max_hours = {
                    "next_6h": 6,
                    "next_12h": 12,
                    "next_24h": 24,
                    "next_48h": 48,
                    "next_3d": 72,
                    "next_7d": 24 * 7,
                    "next_30d": 24 * 30,
                }.get(expiry_filter)
            if max_hours is not None:
                if event_time is None:
                    continue
                if hours_remaining is None or hours_remaining < 0 or hours_remaining > max_hours:
                    continue

            rows.append({
                "market_id": (row.get("market_id") or "").strip(),
                "question": question,
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
                "alert_ts": alert_ts,
                "alert_ts_raw": alert_ts_raw,
                "alert_ts_display": alert_ts_display,
                "alert_date_param": alert_date_param,
                "gamma": gamma,
                "edge": edge,
                "gamma_display": f"{gamma:.4f}" if gamma is not None else "—",
                "edge_pct": edge_pct,
                "category": cat.upper(),
                "event_time": event_time,
                "resolution_time_display": resolution_time_display,
                "hours_remaining": hours_remaining,
                "hours_remaining_display": f"{hours_remaining:.1f}h" if hours_remaining is not None and hours_remaining >= 0 else ("Expired" if hours_remaining is not None else "—"),
                "countdown": countdown,
            })
    except (IOError, csv.Error):
        return []

    if sort not in POSITIONS_SORT_OPTIONS:
        sort = "cost_desc"

    def _sort_key(p):
        if sort == "cost_desc":
            return (-p["cost_usd"],)
        if sort == "cost_asc":
            return (p["cost_usd"],)
        if sort == "pnl_desc":
            return (-p["unrealized_pnl"],)
        if sort == "pnl_asc":
            return (p["unrealized_pnl"],)
        if sort == "gamma_desc":
            return (-(p.get("gamma") or 0),)
        if sort == "gamma_asc":
            return ((p.get("gamma") or 0),)
        if sort == "edge_desc":
            return (-(p.get("edge") or 0),)
        if sort == "edge_asc":
            return ((p.get("edge") or 0),)
        if sort == "date_desc":
            ts = p.get("alert_ts")
            return (-(ts.timestamp() if ts else 0),)
        if sort == "date_asc":
            ts = p.get("alert_ts")
            return ((ts.timestamp() if ts else 0),)
        if sort == "expiry_asc":
            et = p.get("event_time")
            return ((et.timestamp() if et else float("inf")),)
        if sort == "expiry_desc":
            et = p.get("event_time")
            return (-(et.timestamp() if et else 0),)
        return (-p["cost_usd"],)

    if sort in ("question_asc", "question_desc"):
        rows.sort(key=lambda p: (p.get("question") or "").lower(), reverse=(sort == "question_desc"))
    else:
        rows.sort(key=_sort_key)

    return rows


# Risky strategy: config via env or defaults (edge_min as decimal, gamma_max, expiry_hours_max)
def get_risky_criteria() -> dict:
    """Return risky strategy criteria: edge_min (decimal), gamma_max, expiry_hours_max. Used for Risky tab."""
    edge_min = 0.01
    try:
        e = (os.getenv("RISKY_EDGE_MIN_PCT") or "").strip()
        if e:
            edge_min = float(e) / 100.0
    except (ValueError, TypeError):
        pass
    gamma_max = 0.94
    try:
        g = (os.getenv("RISKY_GAMMA_MAX") or "").strip()
        if g:
            gamma_max = float(g)
    except (ValueError, TypeError):
        pass
    expiry_hours_max = 48.0
    try:
        h = (os.getenv("RISKY_EXPIRY_HOURS_MAX") or "").strip()
        if h:
            expiry_hours_max = float(h)
    except (ValueError, TypeError):
        pass
    return {"edge_min": edge_min, "gamma_max": gamma_max, "expiry_hours_max": expiry_hours_max}


def get_risky_positions(
    data_path: str,
    days: Optional[int] = None,
    from_date: Optional[str] = None,
    sort: str = "cost_desc",
    strategy: Optional[str] = None,
) -> list[dict]:
    """
    Return open positions that match the Risky strategy criteria (high edge, low gamma, short expiry).
    Uses get_open_positions then filters by RISKY_EDGE_MIN_PCT, RISKY_GAMMA_MAX, RISKY_EXPIRY_HOURS_MAX.
    Excludes expired positions (only currently risky, short-dated).
    """
    criteria = get_risky_criteria()
    edge_min = criteria["edge_min"]
    gamma_max = criteria["gamma_max"]
    expiry_hours_max = criteria["expiry_hours_max"]

    all_positions = get_open_positions(
        data_path,
        days=days,
        from_date=from_date,
        category=None,
        sort=sort,
        expiry_filter=None,
        hours_max=None,
        strategy=strategy,
    )
    risky = []
    for p in all_positions:
        edge = p.get("edge")
        gamma = p.get("gamma")
        hours_remaining = p.get("hours_remaining")
        if edge is None or edge < edge_min:
            continue
        if gamma is None or gamma > gamma_max:
            continue
        if hours_remaining is None:
            continue
        if hours_remaining < 0 or hours_remaining > expiry_hours_max:
            continue
        risky.append(p)
    return risky


def get_interesting_ids(data_path: str) -> set[str]:
    """
    Load set of market_ids marked as interesting from interesting_positions.json.
    File lives in POLYMARKET_DATA_PATH. Returns empty set if file missing or invalid.
    """
    if not data_path or not os.path.isdir(data_path):
        return set()
    path = os.path.join(data_path, INTERESTING_POSITIONS_FILENAME)
    if not os.path.isfile(path):
        return set()
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ids = data.get("market_ids") if isinstance(data, dict) else data
        if isinstance(ids, list):
            return set(str(x).strip() for x in ids if x)
        return set()
    except (json.JSONDecodeError, IOError, TypeError):
        return set()


def toggle_interesting(data_path: str, market_id: str) -> bool:
    """
    Toggle market_id in the interesting set. Returns True if now interesting, False if removed.
    Persists to interesting_positions.json in data_path.
    """
    if not data_path or not os.path.isdir(data_path):
        return False
    market_id = (market_id or "").strip()
    if not market_id:
        return False
    import json
    path = os.path.join(data_path, INTERESTING_POSITIONS_FILENAME)
    current = get_interesting_ids(data_path)
    if market_id in current:
        current.discard(market_id)
        is_now = False
    else:
        current.add(market_id)
        is_now = True
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"market_ids": sorted(current)}, f, indent=2)
        return is_now
    except IOError:
        return not is_now  # revert to previous state on write failure


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


def get_expectancy_by_bands(data_path: str, days: Optional[int] = None, strategy: Optional[str] = None) -> dict:
    """
    Compute expectancy by edge and gamma bands from resolved alerts.
    Returns { "edge_bands": [...], "gamma_bands": [...] }.
    strategy: if set, only include rows with strategy_id == strategy (v3).
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
    raw_rows = _filter_sent_rows(raw_rows)
    if strategy and strategy.strip():
        raw_rows = [r for r in raw_rows if (r.get("strategy_id") or "").strip() == strategy.strip()]

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


def get_loss_breakdown(data_path: str, days: Optional[int] = None, strategy: Optional[str] = None) -> list[dict]:
    """
    Analyze losses by market category (politics, sports, crypto, etc.).
    Returns list of dicts: category, count, pnl, examples (up to 3).
    strategy: if set, only include rows with strategy_id == strategy (v3).
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
    raw_rows = _filter_sent_rows(raw_rows)
    if strategy and strategy.strip():
        raw_rows = [r for r in raw_rows if (r.get("strategy_id") or "").strip() == strategy.strip()]

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
    from_date: Optional[str] = None,
    strategy: Optional[str] = None,
) -> Optional[tuple[list[dict], int]]:
    """
    Read debug candidates CSV from polymarket-alerts. Filename from POLYMARKET_DEBUG_CSV
    (default: debug_candidates.csv). Falls back to debug_candidates_v60.csv then any debug_candidates*.csv.
    Returns (rows, total_count). Used for Loop Summary tab.
    status_filter: "all" | "alert" – when "alert", only rows with status ALERT.
    sort: date_desc | date_asc | edge_desc | edge_asc | question_asc | question_desc | status
    from_date: if set (YYYY-MM-DD), only include ts >= that date.
    strategy: if set, only include rows with strategy_id == strategy (v3).
    """
    if not data_path or not os.path.isdir(data_path):
        return None

    import glob
    default_name = os.getenv("POLYMARKET_DEBUG_CSV", "debug_candidates.csv")
    candidates = [
        os.path.join(data_path, default_name),
        os.path.join(data_path, "debug_candidates_v60.csv"),  # backward compat
    ]
    csv_path = None
    for p in candidates:
        if os.path.isfile(p):
            csv_path = p
            break
    if not csv_path:
        matches = glob.glob(os.path.join(data_path, "debug_candidates*.csv"))
        csv_path = matches[0] if matches else None
    if not csv_path or not os.path.isfile(csv_path):
        return None

    result = _read_csv_cached(csv_path)
    if result is None:
        return None
    _, raw_rows = result
    if strategy and strategy.strip():
        raw_rows = [r for r in raw_rows if (r.get("strategy_id") or "").strip() == strategy.strip()]

    rows = []
    try:
        for row in raw_rows:
            edge = _parse_float(row.get("edge"))
            ts_raw = row.get("ts", "")
            dt = _parse_date(ts_raw)
            ts_display = format_ts_display(dt, ts_raw)
            ts_date_param = dt.strftime("%Y-%m-%d") if dt else ""
            question = (row.get("question") or "").strip()
            # Use link from CSV (actual event URL); fallback to search only when missing
            link = (row.get("link") or "").strip()
            if not link or not link.startswith("http"):
                q_enc = urllib.parse.quote_plus(question.replace("?", "%3F")) if question else ""
                link = f"https://polymarket.com/search?q={q_enc}" if q_enc else ""
            rows.append({
                "ts": ts_raw,
                "ts_dt": dt,
                "ts_display": ts_display,
                "ts_date_param": ts_date_param,
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
                "strategy_id": (row.get("strategy_id") or "").strip(),
            })
    except (IOError, csv.Error):
        return None

    # Status filter
    if status_filter == "alert":
        rows = [r for r in rows if (r.get("status") or "").strip().upper() == "ALERT"]

    # from_date filter
    if from_date and len(from_date) >= 10:
        try:
            cutoff_dt = datetime.strptime(from_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            rows = [r for r in rows if r.get("ts_dt") and (r["ts_dt"].replace(tzinfo=timezone.utc) if r["ts_dt"].tzinfo is None else r["ts_dt"]) >= cutoff_dt]
        except ValueError:
            pass

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


def get_analytics_json(data_path: str) -> Optional[dict]:
    """
    Load analytics.json from polymarket-alerts (from analytics_export.py).
    Returns dict with edge_quality, timing, strategy_cohort, exit_study, totals; or None if missing.
    """
    if not data_path or not os.path.isdir(data_path):
        return None
    import json
    path = os.path.join(data_path, "analytics.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return None


def get_lifecycle_json(data_path: str) -> Optional[dict]:
    """
    Load lifecycle.json from polymarket-alerts (from evaluate_strategy_lifecycle.py).
    Returns dict with strategies, thresholds_used, generated_at; or None if missing.
    """
    if not data_path or not os.path.isdir(data_path):
        return None
    import json
    path = os.path.join(data_path, "lifecycle.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return None


def _format_file_age(mtime: float) -> str:
    """Format a file mtime as 'X min ago' / 'X hours ago' / 'X days ago'."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).timestamp()
    delta_sec = max(0, now - mtime)
    if delta_sec < 60:
        return "just now"
    if delta_sec < 3600:
        mins = int(delta_sec / 60)
        return f"{mins} min ago"
    if delta_sec < 86400:
        hours = int(delta_sec / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(delta_sec / 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


def get_analytics_file_age(data_path: str) -> Optional[str]:
    """Return human-readable age of analytics.json, or None if missing."""
    if not data_path or not os.path.isdir(data_path):
        return None
    path = os.path.join(data_path, "analytics.json")
    if not os.path.isfile(path):
        return None
    try:
        return _format_file_age(os.path.getmtime(path))
    except OSError:
        return None


def get_lifecycle_file_age(data_path: str) -> Optional[str]:
    """Return human-readable age of lifecycle.json, or None if missing."""
    if not data_path or not os.path.isdir(data_path):
        return None
    path = os.path.join(data_path, "lifecycle.json")
    if not os.path.isfile(path):
        return None
    try:
        return _format_file_age(os.path.getmtime(path))
    except OSError:
        return None
