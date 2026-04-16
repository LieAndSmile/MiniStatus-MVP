"""Parse helpers for polymarket CSV / alert rows."""
from datetime import datetime, timezone
from typing import Optional


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


def _parse_iso_datetime(val: str) -> Optional[datetime]:
    """Parse ISO datetime string with or without timezone; return tz-aware UTC if possible."""
    if not val or not isinstance(val, str):
        return None
    s = val.strip()
    if not s:
        return None
    try:
        # Handle trailing Z
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _is_resolved_row(row: dict) -> bool:
    """Infer resolved status from CSV row (works for older and newer rows)."""
    resolved_val = row.get("resolved", "")
    actual_result = (row.get("actual_result") or "").strip().upper()
    return _parse_bool(resolved_val) or actual_result in ("YES", "NO")
