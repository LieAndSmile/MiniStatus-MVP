"""
Data quality flag checks for Polymarket views.
Returns a list of active warnings to render as persistent banners.
Each flag: {"severity": "warning"|"info", "message": str}
"""
import json
import os

from app.utils.polymarket import _read_csv_cached, _parse_float, _is_resolved_row


def _count_sent_resolved(rows: list) -> int:
    """Resolved trades that count toward Portfolio (status=sent only; legacy = no status column)."""
    if not rows:
        return 0
    no_status_col = "status" not in (rows[0] or {})
    n = 0
    for r in rows:
        if not no_status_col and (r.get("status") or "").strip().lower() != "sent":
            continue
        if _is_resolved_row(r):
            n += 1
    return n


def _cohort_resolved_sum(analytics_path: str) -> int:
    try:
        with open(analytics_path, encoding="utf-8") as f:
            aj = json.load(f)
    except (OSError, ValueError, json.JSONDecodeError):
        return 0
    cohort = aj.get("strategy_cohort") or {}
    if not isinstance(cohort, dict):
        return 0
    total = 0
    for v in cohort.values():
        if isinstance(v, dict):
            total += int(v.get("resolved_count") or 0)
    return total


def get_data_quality_flags(data_path: str) -> list:
    flags = []
    if not data_path:
        return flags

    # 0. Stale analytics.json vs live alerts_log (e.g. log repaired to header-only)
    alerts_path = os.path.join(data_path, "alerts_log.csv")
    analytics_path = os.path.join(data_path, "analytics.json")
    if os.path.isfile(alerts_path) and os.path.isfile(analytics_path):
        result = _read_csv_cached(alerts_path)
        csv_n = _count_sent_resolved(result[1] if result else [])
        json_n = _cohort_resolved_sum(analytics_path)
        if csv_n == 0 and json_n > 0:
            flags.append({
                "severity": "warning",
                "message": (
                    "Portfolio reads live alerts_log.csv (sent trades only); analytics.json still shows "
                    f"{json_n} resolved cohort trade(s). Regenerate analytics after restoring the log, or click "
                    "Refresh analytics on the Analytics tab so JSON matches the CSV."
                ),
            })

    # 1. Unrealized PnL all zero → live pricing not running
    positions_path = os.path.join(data_path, "open_positions.csv")
    result = _read_csv_cached(positions_path)
    if result:
        _, rows = result
        if rows and all(_parse_float(r.get("unrealized_pnl")) == 0.0 for r in rows):
            flags.append({
                "severity": "info",
                "message": (
                    "Live pricing unavailable — unrealized P/L shows cost basis only. "
                    "Run update_open_positions.py (without --no-live) to fetch current prices."
                ),
            })

    # 2. Drift data sparse → backfill_drift.py not catching new alerts
    exec_path = os.path.join(data_path, "execution_log.csv")
    result = _read_csv_cached(exec_path)
    if result:
        _, rows = result
        if len(rows) > 50:
            filled_5m = sum(
                1 for r in rows if (r.get("price_5m_after") or "").strip()
            )
            if filled_5m < 10:
                flags.append({
                    "severity": "info",
                    "message": (
                        f"Drift data sparse — {filled_5m} of {len(rows)} execution rows "
                        "have 5m price data. Drift columns populate in real time as new "
                        "alerts age through their windows."
                    ),
                })

    return flags
