"""
Data quality flag checks for Polymarket views.
Returns a list of active warnings to render as persistent banners.
Each flag: {"severity": "warning"|"info", "message": str}
"""
import os
from app.utils.polymarket import _read_csv_cached, _parse_float


def get_data_quality_flags(data_path: str) -> list:
    flags = []
    if not data_path:
        return flags

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
