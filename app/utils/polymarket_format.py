"""Display formatting for polymarket UI (USD, timestamps, labels)."""
from datetime import datetime, timezone
from typing import Optional


def format_compact_usd(val: float) -> str:
    """Format USD with compact notation for large amounts (e.g. $266.5K, $1.2M)."""
    if val >= 1_000_000:
        return f"${val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"${val / 1_000:.1f}K"
    return f"${val:.2f}"


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


def format_resolution_result_detail(actual_result: str, outcome_label: str) -> str:
    """
    Tie YES/NO to the outcome side stored at alert time (e.g. Over/Under, team name).
    When outcome_label is missing (legacy rows), returns YES or NO only.
    """
    ar = (actual_result or "").strip().upper()
    side = (outcome_label or "").strip()
    if ar not in ("YES", "NO"):
        return ar or "—"
    if not side:
        return ar
    if ar == "YES":
        return f"{ar} — {side} hit"
    return f"{ar} — {side} lost"


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


def _format_time_ago(dt: Optional[datetime]) -> str:
    """Human-readable "X min ago" from a tz-aware datetime."""
    if not dt:
        return "—"
    now = datetime.now(timezone.utc)
    delta_sec = (now - dt).total_seconds()
    if delta_sec < 60:
        return "just now"
    if delta_sec < 3600:
        mins = int(delta_sec // 60)
        return f"{mins} min ago"
    if delta_sec < 86400:
        hours = int(delta_sec // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(delta_sec // 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


def _format_file_age(mtime: float) -> str:
    """Format a file mtime as 'X min ago' / 'X hours ago' / 'X days ago'."""
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
