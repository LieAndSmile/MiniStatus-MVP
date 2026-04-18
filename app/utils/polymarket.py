"""
Polymarket Alerts integration - reads CSV data from polymarket-alerts directory.
"""
import copy
import csv
import json
import os
import re
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal

from app.utils.polymarket_constants import (
    SUPPORTED_JSON_ARTIFACT_SCHEMA_VERSION,
    SPORT_DISPLAY_LABELS,
    _CF_STANDARD_BET,
)

# mtime cache: filepath -> (mtime, fieldnames, rows). Invalidates when file changes.
_CSV_CACHE: dict[str, tuple[float, list[str], list[dict]]] = {}


def _read_csv_cached(
    filepath: str,
    required_columns: Optional[tuple[str, ...]] = None,
) -> Optional[tuple[list[str], list[dict]]]:
    """
    Read CSV with mtime caching. Returns (fieldnames, rows) or None.
    Cache invalidates automatically when file mtime changes.
    If required_columns is set and the default comma read is missing any of them,
    tries csv.Sniffer to detect delimiter (e.g. semicolon) and re-reads.
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
        with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        # If caller expects certain columns and we don't have them, try sniffing delimiter
        if required_columns and fieldnames:
            headers_lower = [h.strip().lower() for h in fieldnames if h]
            missing = [c for c in required_columns if c.lower() not in headers_lower]
            if missing:
                try:
                    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f2:
                        sample = f2.read(4096)
                    if sample and "\n" in sample:
                        try:
                            sniffer = csv.Sniffer()
                            dialect = sniffer.sniff(sample, delimiters=",;\t")
                            with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f3:
                                reader2 = csv.DictReader(f3, dialect=dialect)
                                fn2 = list(reader2.fieldnames or [])
                                rows2 = list(reader2)
                            fn2_lower = [h.strip().lower() for h in fn2 if h]
                            if all(c.lower() in fn2_lower for c in required_columns):
                                fieldnames, rows = fn2, rows2
                        except (csv.Error, Exception):
                            pass
                except (IOError, OSError):
                    pass
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

# v3: strategy filter options (match strategies.yaml; extended for Phase 1–3 probes and strategy rework)
STRATEGY_OPTIONS = (
    "safe",
    "safe_fast",
    "safe_premium",
    "safe_swing_low_gamma",
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

STRATEGY_LABELS: dict[str, str] = {
    "safe": "Safe (legacy)",
    "safe_fast": "Safe fast",
    "safe_premium": "Safe premium",
    "safe_swing_low_gamma": "Safe swing / low γ",
    "safe_v2": "Safe v2",
    "same_day_probe": "Same-day probe",
    "hold_3to7d_probe": "Hold 3–7d probe",
    "hold_8to10d_probe": "Hold 8–10d probe",
    "gamma_84_86_probe": "Gamma 84–86 probe",
    "gamma_86_92_probe": "Gamma 86–92 probe",
    "gamma_92_96_probe": "Gamma 92–96 probe",
    "mid_gamma": "Mid gamma",
    "resolution_sprint": "Resolution sprint",
}

STRATEGY_MODE: dict[str, str] = {
    "safe": "disabled",
    "safe_fast": "active",
    "safe_premium": "active",
    "safe_swing_low_gamma": "shadow",
    "safe_v2": "shadow",
    "same_day_probe": "shadow",
    "hold_3to7d_probe": "shadow",
    "hold_8to10d_probe": "shadow",
    "gamma_84_86_probe": "shadow",
    "gamma_86_92_probe": "shadow",
    "gamma_92_96_probe": "shadow",
    "mid_gamma": "shadow",
    "resolution_sprint": "shadow",
}


BLOCK_REASON_LABELS: dict[str, str] = {
    "MAX_TOTAL_RISK_USD": "Portfolio cap reached",
    "MAX_OPEN_POSITIONS": "Max positions open",
    "MAX_CATEGORY_EXPOSURE_USD": "Category limit reached",
    "MAX_STRATEGY_EXPOSURE_USD": "Strategy limit reached",
    "sport_not_enabled_for_safe_execution": "Sport not enabled for safe execution",
    "blocked_inactive_strategy": "Strategy inactive",
}


def _safe_execution_sports() -> set[str]:
    raw = (os.getenv("SAFE_EXECUTION_SPORTS") or "").strip()
    if raw:
        return {x.strip().lower() for x in raw.split(",") if x.strip()}
    return {"soccer", "tennis", "nba", "nhl", "mlb"}


def _parse_pnl_numeric(row: dict) -> Optional[float]:
    """Return float pnl if column is present and numeric; else None (not resolved for scorecard)."""
    raw = row.get("pnl_usd")
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _scorecard_row_cost_usd(row: dict) -> float:
    """Cost basis for ROI denominator (resolved rows). Prefer cost_usd, else bet_size_usd."""
    c = _parse_float(row.get("cost_usd"))
    if c > 0:
        return c
    return _parse_float(row.get("bet_size_usd"))


def get_strategy_scorecard(
    data_path: str,
    safe_scope: Literal["safe_only", "all_tracked"] = "safe_only",
    days: Optional[int] = None,
) -> list[dict]:
    """
    Per-strategy aggregates from alerts_log.csv: only status=sent rows.
    Resolved = resolved flag truthy and pnl_usd parseable as a number.
    No UI; read-only over existing columns.
    """
    if not data_path or not os.path.isdir(data_path):
        return []
    csv_path = os.path.join(data_path, "alerts_log.csv")
    cached = _read_csv_cached(csv_path)
    if not cached:
        return []
    _, rows = cached

    cutoff: Optional[datetime] = None
    if days is not None and int(days) > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(days))

    allowed_sports: Optional[set[str]]
    if safe_scope == "all_tracked":
        allowed_sports = None
    else:
        allowed_sports = _safe_execution_sports()

    def row_in_scope(row: dict) -> bool:
        if allowed_sports is not None:
            sp = (row.get("sport") or "").strip().lower()
            if sp not in allowed_sports:
                return False
        if cutoff is not None:
            ts = _parse_iso_datetime(row.get("ts") or "") or _parse_date(row.get("ts"))
            if ts is None:
                return False
            ts_utc = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)
            if ts_utc < cutoff:
                return False
        return True

    # strategy_id -> aggregates
    sent: dict[str, int] = defaultdict(int)
    resolved_n: dict[str, int] = defaultdict(int)
    wins: dict[str, int] = defaultdict(int)
    losses: dict[str, int] = defaultdict(int)
    realized: dict[str, float] = defaultdict(float)
    cost_sum: dict[str, float] = defaultdict(float)
    last_ts: dict[str, Optional[datetime]] = defaultdict(lambda: None)

    for row in rows:
        if not row_in_scope(row):
            continue
        if (row.get("status") or "").strip().lower() != "sent":
            continue
        sid = (row.get("strategy_id") or "").strip() or "(unknown)"
        sent[sid] += 1
        ts = _parse_iso_datetime(row.get("ts") or "") or _parse_date(row.get("ts"))
        if ts is not None:
            ts_utc = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)
            prev = last_ts[sid]
            if prev is None or ts_utc > prev:
                last_ts[sid] = ts_utc

        res_flag = _parse_bool(row.get("resolved"))
        pnl_opt = _parse_pnl_numeric(row)
        if res_flag and pnl_opt is not None:
            resolved_n[sid] += 1
            realized[sid] += pnl_opt
            cost_sum[sid] += _scorecard_row_cost_usd(row)
            if pnl_opt > 0:
                wins[sid] += 1
            else:
                losses[sid] += 1

    out: list[dict] = []
    for sid in sent:
        rn = resolved_n[sid]
        rpnl = round(realized[sid], 2)
        ctot = cost_sum[sid]
        roi = (rpnl / ctot) if ctot > 0 else 0.0
        wr = (wins[sid] / rn) if rn else 0.0
        lt = last_ts[sid]
        last_sent_ts = lt.isoformat() if lt else ""
        out.append(
            {
                "strategy_id": sid,
                "sent": sent[sid],
                "resolved": rn,
                "wins": wins[sid],
                "losses": losses[sid],
                "win_rate": round(wr, 6),
                "realized_pnl_usd": rpnl,
                "roi_pct": round(roi, 6),
                "cost_usd_total": round(ctot, 2),
                "sample_warning": rn < 30,
                "last_sent_ts": last_sent_ts,
            }
        )

    out.sort(key=lambda x: x["realized_pnl_usd"], reverse=True)
    return out


def get_strategy_options_grouped(strategy_options: tuple[str, ...]) -> list[dict]:
    """
    Group strategy options by mode for the nav dropdown.

    Note: we treat *_probe strategies as "Probes" (separate group) even though STRATEGY_MODE marks them as "shadow".
    This matches strategies.yaml naming and avoids extra IO on every request.
    """
    active: list[str] = []
    shadow: list[str] = []
    probes: list[str] = []
    disabled: list[str] = []

    for opt in strategy_options or ():
        mode = STRATEGY_MODE.get(opt, "")
        if opt.endswith("_probe"):
            probes.append(opt)
        elif mode == "active":
            active.append(opt)
        elif mode == "shadow":
            shadow.append(opt)
        else:
            disabled.append(opt)

    def _sorted(xs: list[str]) -> list[str]:
        return sorted(xs, key=lambda x: (x or "").lower())

    return [
        {"group": "active", "label": "● Active", "options": _sorted(active)},
        {"group": "shadow", "label": "◎ Shadow (observing)", "options": _sorted(shadow)},
        {"group": "probes", "label": "◎ Probes", "options": _sorted(probes)},
        {"group": "disabled", "label": "— Disabled", "options": _sorted(disabled)},
    ]


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


def _is_resolved_row(row: dict) -> bool:
    """Infer resolved status from CSV row (works for older and newer rows)."""
    resolved_val = row.get("resolved", "")
    actual_result = (row.get("actual_result") or "").strip().upper()
    return _parse_bool(resolved_val) or actual_result in ("YES", "NO")


def get_bankroll_status(data_path: str) -> dict:
    """
    Read bankroll.json and return display-ready status for UI.

    open_positions_count is derived from alerts_log.csv: count of status='sent' rows that are not resolved yet.
    """
    status = {
        "total": None,
        "deployed": None,
        "available": None,
        "deployed_pct": None,
        "last_updated_display": "—",
        "open_positions_count": 0,
        "sport_open": [],
    }

    if not data_path or not os.path.isdir(data_path):
        return status

    # Open positions count
    csv_path = os.path.join(data_path, "alerts_log.csv")
    result = _read_csv_cached(csv_path) if os.path.isfile(csv_path) else None
    if result is not None:
        _, rows = result
        if rows:
            # Only count rows that the simulation would have "placed" (sent), but not resolved yet.
            open_cnt = 0
            sport_deploy: dict[str, dict[str, float]] = {}
            for row in rows:
                st = (row.get("status") or "").strip().lower()
                if st != "sent":
                    continue
                if not _is_resolved_row(row):
                    open_cnt += 1
                    sk = (row.get("sport") or "").strip().lower()
                    if sk in ("nba", "nhl", "mlb"):
                        stake = _parse_float(row.get("bet_size_usd"), default=0.0)
                        if sk not in sport_deploy:
                            sport_deploy[sk] = {"count": 0.0, "deployed_usd": 0.0}
                        sport_deploy[sk]["count"] += 1.0
                        sport_deploy[sk]["deployed_usd"] += stake
            status["open_positions_count"] = open_cnt
            status["sport_open"] = [
                {
                    "sport": k,
                    "count": int(v["count"]),
                    "deployed_usd": v["deployed_usd"],
                    "deployed_display": format_compact_usd(v["deployed_usd"]),
                }
                for k, v in sorted(sport_deploy.items())
            ]

    # Bankroll file
    bankroll_path = os.path.join(data_path, "bankroll.json")
    try:
        if os.path.isfile(bankroll_path):
            import json
            with open(bankroll_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            total = data.get("total")
            deployed = data.get("deployed")
            available = data.get("available")
            status["total"] = float(total) if total is not None and str(total) != "" else None
            status["deployed"] = float(deployed) if deployed is not None and str(deployed) != "" else None
            status["available"] = float(available) if available is not None and str(available) != "" else None
            if status["total"] is not None and status["deployed"] is not None and status["total"] > 0:
                status["deployed_pct"] = (status["deployed"] / status["total"]) * 100.0

            last_updated = data.get("last_updated") or ""
            dt = _parse_iso_datetime(last_updated)
            if dt:
                status["last_updated_display"] = _format_time_ago(dt)
            else:
                # fallback: file mtime
                status["last_updated_display"] = _format_time_ago(datetime.fromtimestamp(os.path.getmtime(bankroll_path), tz=timezone.utc))
    except Exception:
        # Keep UI resilient: show open_positions_count even if bankroll.json is broken.
        pass

    return status


def get_strategy_summary(data_path: str) -> list[dict]:
    """
    Build strategy overview rows for the Portfolio "Command Center" panel.
    Source: polymarket-alerts `strategies.yaml`.
    """
    empty = [
        {"group": "active", "label": "● ACTIVE", "items": [], "count": 0},
        {"group": "shadow", "label": "◎ SHADOW — observing, not betting", "items": [], "count": 0},
        {"group": "probes", "label": "◎ PROBES — observing cohorts", "items": [], "count": 0},
        {"group": "disabled", "label": "— DISABLED (legacy)", "items": [], "count": 0},
    ]
    if not data_path or not os.path.isdir(data_path):
        return empty

    yaml_path = os.path.join(data_path, "strategies.yaml")
    if not os.path.isfile(yaml_path):
        return empty

    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception:
        return empty

    if not isinstance(raw, dict):
        return empty

    def _float_or_none(v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    grouped: dict[str, list[dict]] = {"active": [], "shadow": [], "probes": [], "disabled": []}
    for sid, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        # Prefer strategies.yaml, but fall back to STRATEGY_MODE.
        mode = entry.get("mode") or STRATEGY_MODE.get(sid, "disabled")
        family = entry.get("strategy_family") or ""
        is_probe = family == "probe" or (sid or "").endswith("_probe")

        gamma_min = _float_or_none(entry.get("gamma_min"))
        gamma_max = _float_or_none(entry.get("gamma_max"))
        edge_min = _float_or_none(entry.get("edge_min"))
        res_min = entry.get("resolution_days_min")
        res_max = entry.get("resolution_days_max")
        size_multiplier = entry.get("size_multiplier")
        if size_multiplier is None:
            # Mirror backend behavior: unspecified => 1.0 sizing multiplier.
            size_multiplier = 1.0
        try:
            size_multiplier = float(size_multiplier)
        except (ValueError, TypeError):
            size_multiplier = 1.0

        def _fmt_gamma():
            if gamma_min is None and gamma_max is None:
                return ""
            if gamma_min is not None and gamma_max is None:
                return f"γ ≥ {gamma_min:.2f}"
            if gamma_min is not None and gamma_max is not None:
                return f"γ {gamma_min:.2f}–{gamma_max:.2f}"
            return ""

        def _fmt_edge():
            if edge_min is None:
                return ""
            return f"edge ≥ {edge_min * 100:.0f}%"

        def _fmt_res():
            if res_min is None and res_max is None:
                return ""
            try:
                a = int(res_min) if res_min is not None else int(res_max)
                b = int(res_max) if res_max is not None else a
                if a == b:
                    return f"resolves {a}d"
                return f"resolves {a}–{b}d"
            except (ValueError, TypeError):
                return ""

        item = {
            "id": sid,
            "label": STRATEGY_LABELS.get(sid, sid),
            "mode": mode,
            "gamma_edge_res_parts": " · ".join([p for p in [_fmt_gamma(), _fmt_edge(), _fmt_res()] if p]),
            "size_multiplier": size_multiplier,
        }

        if is_probe:
            grouped["probes"].append(item)
        elif mode == "active":
            grouped["active"].append(item)
        elif mode == "shadow":
            grouped["shadow"].append(item)
        else:
            grouped["disabled"].append(item)

    # Order: stable (alphabetical by label)
    for k in grouped:
        grouped[k] = sorted(grouped[k], key=lambda x: (x.get("label") or "").lower())

    result = empty
    mapping = {"active": 0, "shadow": 1, "probes": 2, "disabled": 3}
    for group_name, idx in mapping.items():
        result[idx]["items"] = grouped[group_name]
        result[idx]["count"] = len(grouped[group_name])
    return result


def get_strategy_options_for_nav(data_path: str) -> tuple[str, ...]:
    """
    Return strategy list for nav dropdown. If analytics.json exists, merge its strategy_cohort
    keys with STRATEGY_OPTIONS so any new strategy in data appears; otherwise return STRATEGY_OPTIONS.
    """
    analytics = get_analytics_json(data_path) if data_path else None
    cohort = (analytics or {}).get("strategy_cohort") or {}
    if not isinstance(cohort, dict):
        cohort = {}
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


def get_alerts_status_summary(data_path: str) -> dict:
    """
    Return high-level status and block-reason counts from alerts_log.csv.
    Includes all rows (not only sent) so UI can reflect current operating mode.
    """
    summary = {
        "logged": 0,
        "sent": 0,
        "shadow": 0,
        "blocked": 0,
        "blocked_inactive_strategy": 0,
        "blocked_risk_limit": 0,
        "blocked_ai_screen": 0,
        "top_risk_buckets": [],
        "top_block_reasons": [],
    }
    if not data_path or not os.path.isdir(data_path):
        return summary

    csv_path = os.path.join(data_path, "alerts_log.csv")
    result = _read_csv_cached(csv_path)
    if result is None:
        return summary
    _, rows = result
    if not rows:
        return summary

    block_reasons: dict[str, int] = defaultdict(int)
    risk_buckets: dict[str, int] = defaultdict(int)
    for row in rows:
        summary["logged"] += 1
        status = (row.get("status") or "").strip().lower()
        if status == "sent":
            summary["sent"] += 1
        elif status == "shadow":
            summary["shadow"] += 1
        elif status == "blocked_inactive_strategy":
            summary["blocked"] += 1
            summary["blocked_inactive_strategy"] += 1
            block_reasons["blocked_inactive_strategy"] += 1
        elif status == "blocked_risk_limit":
            summary["blocked"] += 1
            summary["blocked_risk_limit"] += 1
            bucket = (row.get("risk_bucket") or "").strip() or "unknown"
            risk_buckets[bucket] += 1
            reason = (row.get("primary_block_reason") or "").strip()
            if reason:
                block_reasons[reason] += 1
        elif status == "blocked_ai_screen":
            summary["blocked"] += 1
            summary["blocked_ai_screen"] += 1
            reason = (row.get("primary_block_reason") or "").strip()
            if reason:
                block_reasons[reason] += 1
        elif status.startswith("blocked"):
            summary["blocked"] += 1
            reason = (row.get("primary_block_reason") or "").strip()
            if reason:
                block_reasons[reason] += 1

    summary["top_risk_buckets"] = sorted(
        [{"bucket": k, "count": v} for k, v in risk_buckets.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]
    summary["top_block_reasons"] = sorted(
        [{"reason": k, "count": v} for k, v in block_reasons.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:3]
    return summary


def get_recent_decisions(
    data_path: str,
    limit: int = 30,
    status_filter: Optional[str] = None,
    strategy: Optional[str] = None,
) -> list[dict]:
    """
    Read alerts_log.csv and return recent decision rows for UI inspection.

    When status_filter is set, only include rows whose status matches it
    (case-insensitive exact match, e.g. status_filter="sent").
    When strategy is set and not "all", only rows with matching strategy_id.
    """
    if not data_path or not os.path.isdir(data_path):
        return []
    csv_path = os.path.join(data_path, "alerts_log.csv")
    if not os.path.isfile(csv_path):
        return []

    result = _read_csv_cached(csv_path)
    if result is None:
        return []
    _, rows = result
    if not rows:
        return []

    strat = (strategy or "").strip()
    if strat and strat.lower() != "all":
        rows = [r for r in rows if (r.get("strategy_id") or "").strip() == strat]

    decisions: list[dict] = []
    try:
        for row in rows:
            ts_dt = _parse_date(row.get("ts") or row.get("resolved_ts") or row.get("resolved_ts"))
            ts_display = format_ts_display(ts_dt, (row.get("ts") or "").strip())
            status = (row.get("status") or "").strip().lower()
            if status_filter and status != (status_filter or "").strip().lower():
                continue
            strategy_id = (row.get("strategy_id") or "").strip()
            question_raw = row.get("question") or ""
            question = _get_display_label(question_raw)

            bet_size = _parse_float(row.get("bet_size_usd"), default=0.0)
            conviction_score = int(_parse_float(row.get("conviction_score"), default=0.0))

            primary_reason = (row.get("primary_block_reason") or "").strip()
            link = (row.get("link") or "").strip()
            outcome_label = (row.get("outcome_label") or "").strip()
            pick_display = outcome_label or "—"

            # Sent-only view: show resolution outcome if already resolved.
            # Result is blank ("—") until polymarket-alerts resolution_tracker fills
            # actual_result (YES/NO) from the Gamma API after the market closes.
            resolved_val = row.get("resolved", "")
            actual_result = (row.get("actual_result") or "").strip().upper()
            is_resolved = _parse_bool(resolved_val) or actual_result in ("YES", "NO")
            pnl_usd = _parse_float(row.get("pnl_usd"), default=0.0)
            if is_resolved and actual_result in ("YES", "NO"):
                result_display = f"{actual_result} ({pnl_usd:.2f})"
            else:
                result_display = "—"

            sport_raw = (row.get("sport") or "").strip()
            sport_display = SPORT_DISPLAY_LABELS.get(sport_raw.lower(), sport_raw or "—") if sport_raw else "—"
            mt = (row.get("market_type") or "").strip()
            market_type_display = mt or "—"
            ek = (row.get("event_key") or "").strip()
            event_key_display = ek[:48] + "…" if len(ek) > 48 else (ek or "—")

            decisions.append({
                "ts_dt": ts_dt,
                "ts_display": ts_display,
                "status": status,
                "strategy_id": strategy_id,
                "question": question,
                "outcome_label": outcome_label,
                "pick_display": pick_display,
                "sport": sport_raw,
                "sport_display": sport_display,
                "market_type": mt,
                "market_type_display": market_type_display,
                "event_key": ek,
                "event_key_display": event_key_display,
                "bet_size_usd": bet_size,
                "bet_size_display": format_compact_usd(bet_size),
                "conviction_score": conviction_score,
                "primary_block_reason": primary_reason,
                "link": link if link.startswith("http") else "",
                "result_display": result_display,
            })
    except (IOError, csv.Error):
        return []

    # Sort newest first by parsed ts; keep stable behavior if ts missing.
    def _ts_key(d):
        dt = d.get("ts_dt")
        try:
            return dt.timestamp() if dt else 0.0
        except Exception:
            return 0.0

    decisions_sorted = sorted(decisions, key=_ts_key, reverse=True)
    # Keep only newest N visible rows (dict order not used after sorting).
    return decisions_sorted[: max(1, int(limit))] if decisions_sorted else []

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
        result = _read_csv_cached(
            csv_path,
            required_columns=ALERTS_LOG_REQUIRED + ALERTS_LOG_NEEDS_ONE_OF,
        )
        if result is None:
            return False, "Could not read CSV"
        fieldnames, rows = result
        headers = [h.strip() for h in fieldnames if h]
        headers_lower = [h.lower() for h in headers]

        # Check required columns
        missing = [c for c in ALERTS_LOG_REQUIRED if c.lower() not in headers_lower]
        if missing:
            headers_preview = ", ".join(headers[:20]) + (" ..." if len(headers) > 20 else "")
            return False, f"Missing required columns: {', '.join(missing)}. Headers in file ({len(headers)}): {headers_preview}"

        # Need at least one timestamp column
        has_ts = any(c.lower() in headers_lower for c in ALERTS_LOG_NEEDS_ONE_OF)
        if not has_ts:
            headers_preview = ", ".join(headers[:20]) + (" ..." if len(headers) > 20 else "")
            return False, f"Missing timestamp column (need 'ts' or 'resolved_ts'). Headers in file ({len(headers)}): {headers_preview}"

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
                    # For status=sent rows, these fields are present for dynamic sizing.
                    "bet_size_usd": _parse_float(row.get("bet_size_usd") or row.get("cost_usd") or row.get("fill_usdc") or 0.0),
                    "conviction_score": int(_parse_float(row.get("conviction_score"), default=0.0)),
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
        # These may be missing on legacy rows; ensure template always has the fields.
        if "bet_size_usd" not in r:
            r["bet_size_usd"] = 0.0
        if "conviction_score" not in r:
            r["conviction_score"] = 0
        r["bet_size_display"] = format_compact_usd(r["bet_size_usd"] or 0.0)
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
    edge_min: Optional[float] = None,
    gamma_max: Optional[float] = None,
    expiry_hours_max: Optional[float] = None,
) -> list[dict]:
    """
    Return open positions that match the Risky strategy criteria (high edge, low gamma, short expiry).
    When edge_min, gamma_max, or expiry_hours_max are provided, they override get_risky_criteria().
    Excludes expired positions (only currently risky, short-dated).
    """
    criteria = get_risky_criteria()
    edge_min = edge_min if edge_min is not None else criteria["edge_min"]
    gamma_max = gamma_max if gamma_max is not None else criteria["gamma_max"]
    expiry_hours_max = expiry_hours_max if expiry_hours_max is not None else criteria["expiry_hours_max"]

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


# Tolerances for "near risky" (plan: edge 0.25 pp, gamma 0.02, expiry 12h)
NEAR_RISKY_EDGE_TOL = 0.0025   # 0.25 percentage points
NEAR_RISKY_GAMMA_TOL = 0.02
NEAR_RISKY_EXPIRY_TOL_HOURS = 12.0


def get_near_risky_positions(
    data_path: str,
    days: Optional[int] = None,
    from_date: Optional[str] = None,
    sort: str = "cost_desc",
    strategy: Optional[str] = None,
    edge_min: Optional[float] = None,
    gamma_max: Optional[float] = None,
    expiry_hours_max: Optional[float] = None,
) -> list[dict]:
    """
    Open positions that narrowly miss one Risky threshold (edge within 0.25 pp,
    gamma within 0.02, expiry within 12h). Excludes positions that already qualify as risky.
    Each returned dict includes near_reason: "edge" | "gamma" | "expiry" (first miss found).
    """
    criteria = get_risky_criteria()
    edge_min = edge_min if edge_min is not None else criteria["edge_min"]
    gamma_max = gamma_max if gamma_max is not None else criteria["gamma_max"]
    expiry_hours_max = expiry_hours_max if expiry_hours_max is not None else criteria["expiry_hours_max"]

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
    def _key_ts(v):
        if v is None:
            return ""
        return str(v).strip() if isinstance(v, str) else str(v)

    risky_set = {
        (p.get("market_id"), _key_ts(p.get("alert_ts")), _key_ts(p.get("question")))
        for p in get_risky_positions(
            data_path, days=days, from_date=from_date, sort=sort, strategy=strategy,
            edge_min=edge_min, gamma_max=gamma_max, expiry_hours_max=expiry_hours_max,
        )
    }

    near = []
    for p in all_positions:
        key = (p.get("market_id"), _key_ts(p.get("alert_ts")), _key_ts(p.get("question")))
        if key in risky_set:
            continue
        edge = p.get("edge")
        gamma = p.get("gamma")
        hours_remaining = p.get("hours_remaining")
        if hours_remaining is not None and hours_remaining < 0:
            continue

        # Narrowly misses edge: within 0.25 pp below min, and passes gamma and expiry
        fails_edge = edge is None or edge < edge_min
        near_edge = (
            edge is not None
            and edge_min - NEAR_RISKY_EDGE_TOL <= edge < edge_min
            and (gamma is not None and gamma <= gamma_max)
            and (hours_remaining is not None and 0 <= hours_remaining <= expiry_hours_max)
        )
        # Narrowly misses gamma: just above max, passes edge and expiry
        fails_gamma = gamma is None or gamma > gamma_max
        near_gamma = (
            gamma is not None
            and gamma_max < gamma <= gamma_max + NEAR_RISKY_GAMMA_TOL
            and (edge is not None and edge >= edge_min)
            and (hours_remaining is not None and 0 <= hours_remaining <= expiry_hours_max)
        )
        # Narrowly misses expiry: just above max, passes edge and gamma
        fails_expiry = hours_remaining is None or hours_remaining > expiry_hours_max
        near_expiry = (
            hours_remaining is not None
            and expiry_hours_max < hours_remaining <= expiry_hours_max + NEAR_RISKY_EXPIRY_TOL_HOURS
            and (edge is not None and edge >= edge_min)
            and (gamma is not None and gamma <= gamma_max)
        )

        if near_edge:
            p = dict(p)
            p["near_reason"] = "edge"
            near.append(p)
        elif near_gamma:
            p = dict(p)
            p["near_reason"] = "gamma"
            near.append(p)
        elif near_expiry:
            p = dict(p)
            p["near_reason"] = "expiry"
            near.append(p)
    return near


def get_risky_historical_performance(
    data_path: str,
    days: Optional[int] = None,
    from_date: Optional[str] = None,
    strategy: Optional[str] = None,
    edge_min: Optional[float] = None,
    gamma_max: Optional[float] = None,
    expiry_hours_max: Optional[float] = None,
) -> dict:
    """
    Historical performance of resolved alerts that would have qualified as Risky
    (edge >= edge_min, gamma <= gamma_max, time-to-resolution <= expiry_hours_max).
    Uses same thresholds as get_risky_criteria() when not passed.
    Returns dict: resolved_count, wins, losses, total_pnl, total_cost, roi_pct,
    avg_edge, avg_gamma, avg_hold_hours, categories (list of {category, count, wins, losses, total_pnl, roi_pct}).
    """
    criteria = get_risky_criteria()
    edge_min = edge_min if edge_min is not None else criteria["edge_min"]
    gamma_max = gamma_max if gamma_max is not None else criteria["gamma_max"]
    expiry_hours_max = expiry_hours_max if expiry_hours_max is not None else criteria["expiry_hours_max"]

    empty = {
        "resolved_count": 0,
        "wins": 0,
        "losses": 0,
        "total_pnl": 0.0,
        "total_pnl_display": "$0.00",
        "total_cost": 0.0,
        "total_cost_display": "$0",
        "roi_pct": None,
        "avg_edge": None,
        "avg_gamma": None,
        "avg_hold_hours": None,
        "categories": [],
    }
    if not data_path or not os.path.isdir(data_path):
        return empty

    csv_path = os.path.join(data_path, "alerts_log.csv")
    if not os.path.isfile(csv_path):
        return empty

    result = _read_csv_cached(csv_path)
    if result is None:
        return empty
    _, raw_rows = result
    raw_rows = _filter_sent_rows(raw_rows)
    if strategy and strategy.strip():
        raw_rows = [r for r in raw_rows if (r.get("strategy_id") or "").strip() == strategy.strip()]

    cutoff = None
    if from_date and len(from_date) >= 10:
        try:
            cutoff = datetime.strptime(from_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    if cutoff is None and days is not None and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    qualifying = []
    try:
        for row in raw_rows:
            resolved_val = row.get("resolved", "")
            actual_result = (row.get("actual_result") or "").strip().upper()
            is_resolved = _parse_bool(resolved_val) or actual_result in ("YES", "NO")
            if not is_resolved:
                continue

            resolved_ts = _parse_date(row.get("resolved_ts") or row.get("ts"))
            ts_alert = _parse_date(row.get("ts"))
            if not resolved_ts:
                continue
            if cutoff is not None:
                ts_aware = resolved_ts.replace(tzinfo=timezone.utc) if resolved_ts.tzinfo is None else resolved_ts
                if ts_aware < cutoff:
                    continue

            edge = _parse_float(row.get("edge"), default=0.0) if row.get("edge") not in (None, "") else None
            gamma = _parse_float(row.get("gamma"), default=0.0) if row.get("gamma") not in (None, "") else None
            hold_hours = None
            if ts_alert and resolved_ts:
                start = ts_alert.replace(tzinfo=timezone.utc) if ts_alert.tzinfo is None else ts_alert
                end = resolved_ts.replace(tzinfo=timezone.utc) if resolved_ts.tzinfo is None else resolved_ts
                delta_sec = (end - start).total_seconds()
                if delta_sec >= 0:
                    hold_hours = delta_sec / 3600.0

            if edge is None or edge < edge_min:
                continue
            if gamma is None or gamma > gamma_max:
                continue
            if hold_hours is None or hold_hours < 0 or hold_hours > expiry_hours_max:
                continue

            pnl = _parse_float(row.get("pnl_usd"), 0.0)
            cost = _parse_float(row.get("cost_usd") or row.get("fill_usdc"), 0.0)
            question = (row.get("question") or "").strip()
            cat = _categorize_question(question)
            qualifying.append({
                "pnl": pnl,
                "cost": cost,
                "edge": edge,
                "gamma": gamma,
                "hold_hours": hold_hours,
                "category": cat,
            })
    except (IOError, csv.Error):
        return empty

    if not qualifying:
        return empty

    total_pnl = sum(r["pnl"] for r in qualifying)
    total_cost = sum(r["cost"] for r in qualifying)
    wins = sum(1 for r in qualifying if r["pnl"] > 0)
    losses = sum(1 for r in qualifying if r["pnl"] < 0)
    roi_pct = (total_pnl / total_cost * 100.0) if total_cost and total_cost > 0 else None
    n = len(qualifying)
    avg_edge = sum(r["edge"] for r in qualifying) / n
    avg_gamma = sum(r["gamma"] for r in qualifying) / n
    avg_hold_hours = sum(r["hold_hours"] for r in qualifying) / n

    by_cat: dict[str, dict] = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "pnl": 0.0, "cost": 0.0})
    for r in qualifying:
        c = r["category"]
        by_cat[c]["count"] += 1
        if r["pnl"] > 0:
            by_cat[c]["wins"] += 1
        else:
            by_cat[c]["losses"] += 1
        by_cat[c]["pnl"] += r["pnl"]
        by_cat[c]["cost"] += r["cost"]

    categories = []
    for cat, data in sorted(by_cat.items(), key=lambda x: -abs(x[1]["pnl"])):
        cat_roi = (data["pnl"] / data["cost"] * 100.0) if data["cost"] and data["cost"] > 0 else None
        categories.append({
            "category": cat.upper(),
            "count": data["count"],
            "wins": data["wins"],
            "losses": data["losses"],
            "total_pnl": round(data["pnl"], 2),
            "total_pnl_display": f"${data['pnl']:.2f}",
            "roi_pct": round(cat_roi, 2) if cat_roi is not None else None,
        })

    return {
        "resolved_count": n,
        "wins": wins,
        "losses": losses,
        "total_pnl": round(total_pnl, 2),
        "total_pnl_display": f"${total_pnl:.2f}",
        "total_cost": round(total_cost, 2),
        "total_cost_display": format_compact_usd(total_cost),
        "roi_pct": round(roi_pct, 2) if roi_pct is not None else None,
        "avg_edge": round(avg_edge, 4),
        "avg_edge_pct": f"{avg_edge * 100:.2f}%",
        "avg_gamma": round(avg_gamma, 4),
        "avg_hold_hours": round(avg_hold_hours, 1),
        "avg_hold_days": round(avg_hold_hours / 24.0, 1),
        "categories": categories,
    }


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


def get_loss_breakdown_buckets(
    data_path: str,
    days: Optional[int] = None,
    strategy: Optional[str] = None,
) -> dict:
    """
    Analyze losing trades by edge, gamma, and hold/time-to-resolution buckets.
    Returns dict with 'edge', 'gamma', 'hold', 'time_to_resolution' lists.
    """
    empty = {"edge": [], "gamma": [], "hold": [], "time_to_resolution": []}
    if not data_path or not os.path.isdir(data_path):
        return empty

    csv_path = os.path.join(data_path, "alerts_log.csv")
    if not os.path.isfile(csv_path):
        return empty

    result = _read_csv_cached(csv_path)
    if result is None:
        return empty
    _, raw_rows = result
    raw_rows = _filter_sent_rows(raw_rows)
    if strategy and strategy.strip():
        raw_rows = [r for r in raw_rows if (r.get("strategy_id") or "").strip() == strategy.strip()]

    edge_buckets_def = [
        ("<0.5%", lambda e: e is not None and e < 0.005),
        ("0.5–1.0%", lambda e: e is not None and 0.005 <= e < 0.01),
        ("1.0–1.25%", lambda e: e is not None and 0.01 <= e < 0.0125),
        ("1.25%+", lambda e: e is not None and e >= 0.0125),
    ]
    gamma_buckets_def = [
        ("<0.80", lambda g: g is not None and g < 0.80),
        ("0.80–0.90", lambda g: g is not None and 0.80 <= g < 0.90),
        ("0.90–0.94", lambda g: g is not None and 0.90 <= g < 0.94),
        ("0.94+", lambda g: g is not None and g >= 0.94),
    ]
    hold_buckets_def = [
        ("Same day", lambda d: d is not None and d < 1.0),
        ("1–3d", lambda d: d is not None and 1.0 <= d < 3.0),
        ("3–7d", lambda d: d is not None and 3.0 <= d < 7.0),
        ("8–10d", lambda d: d is not None and 7.0 <= d < 10.0),
        ("10+d", lambda d: d is not None and d >= 10.0),
    ]

    edge_stats = {label: {"bucket": label, "count": 0, "pnl": 0.0} for label, _ in edge_buckets_def}
    gamma_stats = {label: {"bucket": label, "count": 0, "pnl": 0.0} for label, _ in gamma_buckets_def}
    hold_stats = {label: {"bucket": label, "count": 0, "pnl": 0.0} for label, _ in hold_buckets_def}

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

            resolved_ts = _parse_date(row.get("resolved_ts") or row.get("ts"))
            if days is not None and days > 0 and resolved_ts:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                ts_aware = resolved_ts.replace(tzinfo=timezone.utc) if resolved_ts.tzinfo is None else resolved_ts
                if ts_aware < cutoff:
                    continue

            edge = _parse_float(row.get("edge"), default=0.0) if row.get("edge") not in (None, "") else None
            gamma = _parse_float(row.get("gamma"), default=0.0) if row.get("gamma") not in (None, "") else None

            ts_alert = _parse_date(row.get("ts"))
            hold_days = None
            if ts_alert and resolved_ts:
                start = ts_alert.replace(tzinfo=timezone.utc) if ts_alert.tzinfo is None else ts_alert
                end = resolved_ts.replace(tzinfo=timezone.utc) if resolved_ts.tzinfo is None else resolved_ts
                delta = end - start
                if delta.total_seconds() >= 0:
                    hold_days = delta.total_seconds() / 86400.0

            for label, matcher in edge_buckets_def:
                if matcher(edge):
                    edge_stats[label]["count"] += 1
                    edge_stats[label]["pnl"] += pnl
                    break

            for label, matcher in gamma_buckets_def:
                if matcher(gamma):
                    gamma_stats[label]["count"] += 1
                    gamma_stats[label]["pnl"] += pnl
                    break

            for label, matcher in hold_buckets_def:
                if matcher(hold_days):
                    hold_stats[label]["count"] += 1
                    hold_stats[label]["pnl"] += pnl
                    break
    except (IOError, csv.Error):
        return empty

    def _finalize(stats_dict, order_def):
        result = []
        for label, _ in order_def:
            data = stats_dict.get(label) or {"bucket": label, "count": 0, "pnl": 0.0}
            pnl_val = round(data["pnl"], 2)
            result.append({
                "bucket": label,
                "count": data["count"],
                "pnl": pnl_val,
                "pnl_display": f"${pnl_val:.2f}",
            })
        return result

    edge_list = _finalize(edge_stats, edge_buckets_def)
    gamma_list = _finalize(gamma_stats, gamma_buckets_def)
    hold_list = _finalize(hold_stats, hold_buckets_def)

    return {
        "edge": edge_list,
        "gamma": gamma_list,
        "hold": hold_list,
        "time_to_resolution": hold_list,
    }


def get_loss_trend_by_category(
    data_path: str,
    days: Optional[int] = None,
    strategy: Optional[str] = None,
) -> list[dict]:
    """
    Monthly net P/L trend by category for resolved alerts.
    Returns list of dicts: month (YYYY-MM), total_pnl, total_pnl_display, categories[...].
    Respects days window and strategy filter, uses resolved_ts (fallback ts) for month.
    """
    if not data_path or not os.path.isdir(data_path):
        return []

    csv_path = os.path.join(data_path, "alerts_log.csv")
    if not os.path.isfile(csv_path):
        return []

    result = _read_csv_cached(csv_path)
    if result is None:
        return []
    _, raw_rows = result
    raw_rows = _filter_sent_rows(raw_rows)
    if strategy and strategy.strip():
        raw_rows = [r for r in raw_rows if (r.get("strategy_id") or "").strip() == strategy.strip()]

    by_month_cat: dict[tuple[str, str], float] = defaultdict(float)
    month_totals: dict[str, float] = defaultdict(float)

    try:
        for row in raw_rows:
            resolved_val = row.get("resolved", "")
            actual_result = (row.get("actual_result") or "").strip().upper()
            is_resolved = _parse_bool(resolved_val) or actual_result in ("YES", "NO")
            if not is_resolved:
                continue

            pnl = _parse_float(row.get("pnl_usd", ""))
            resolved_ts = _parse_date(row.get("resolved_ts") or row.get("ts"))
            if not resolved_ts:
                continue

            if days is not None and days > 0:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                ts_aware = resolved_ts.replace(tzinfo=timezone.utc) if resolved_ts.tzinfo is None else resolved_ts
                if ts_aware < cutoff:
                    continue

            month = (resolved_ts.replace(tzinfo=timezone.utc) if resolved_ts.tzinfo is None else resolved_ts).strftime("%Y-%m")
            cat = _categorize_question((row.get("question") or "").strip())
            by_month_cat[(month, cat)] += pnl
            month_totals[month] += pnl
    except (IOError, csv.Error):
        return []

    if not month_totals:
        return []

    months_sorted = sorted(month_totals.keys())
    trend = []
    for m in months_sorted:
        cats = []
        for (month, cat), val in by_month_cat.items():
            if month != m:
                continue
            pnl_val = round(val, 2)
            cats.append({
                "category": cat,
                "pnl": pnl_val,
                "pnl_display": f"${pnl_val:.2f}",
            })
        cats.sort(key=lambda x: x["pnl"])
        total_pnl = round(month_totals[m], 2)
        trend.append({
            "month": m,
            "total_pnl": total_pnl,
            "total_pnl_display": f"${total_pnl:.2f}",
            "categories": cats,
        })
    return trend


DEBUG_SORT_OPTIONS = (
    "date_desc",     # Newest first
    "date_asc",      # Oldest first
    "edge_desc",     # Highest edge first
    "edge_asc",      # Lowest edge first
    "question_asc", # Question A–Z
    "question_desc",# Question Z–A
    "status",       # ALERT first, then EFFECTIVE_OUT
    "hrs_asc",      # Hrs left soonest first
    "hrs_desc",     # Hrs left latest first
)

# Loop/Dev Hrs left filter presets (max hours): same idea as Open Positions expiry filter
LOOP_HOURS_MAX_PRESETS = (6, 12, 24, 48)  # ≤6h, ≤12h, ≤24h, ≤48h


def get_debug_candidates(
    data_path: str,
    limit: int = 5000,
    status_filter: Literal["all", "alert"] = "all",
    sort: str = "date_desc",
    from_date: Optional[str] = None,
    strategy: Optional[str] = None,
    hours_max: Optional[float] = None,
) -> Optional[tuple[list[dict], int]]:
    """
    Read debug candidates CSV from polymarket-alerts. Filename from POLYMARKET_DEBUG_CSV
    (default: debug_candidates.csv). Falls back to debug_candidates_v60.csv then any debug_candidates*.csv.
    Returns (rows, total_count). Used for Loop Summary tab.
    status_filter: "all" | "alert" – when "alert", only rows with status ALERT.
    sort: date_desc | date_asc | edge_desc | edge_asc | question_asc | question_desc | status | hrs_asc | hrs_desc
    from_date: if set (YYYY-MM-DD), only include ts >= that date.
    strategy: if set, only include rows with strategy_id == strategy (v3).
    hours_max: if set, only include rows with 0 <= hrs_left <= hours_max (filter by hours left).
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
            # Resolution / Hrs left: recompute from event_time at display time so past events show "Expired"
            event_time_raw = (row.get("event_time") or "").strip()
            event_time_dt = _parse_date(event_time_raw) if event_time_raw else None
            resolution_display = format_ts_display(event_time_dt, event_time_raw)
            now = datetime.now(timezone.utc)
            if event_time_dt is not None:
                et = event_time_dt.replace(tzinfo=timezone.utc) if event_time_dt.tzinfo is None else event_time_dt
                hrs_left_float = (et - now).total_seconds() / 3600.0
                if hrs_left_float < 0:
                    hrs_left_display = "Expired"
                elif hrs_left_float >= 24:
                    hrs_left_display = f"{int(hrs_left_float // 24)}d"
                else:
                    hrs_left_display = f"{hrs_left_float:.1f}h"
            else:
                hrs_left_val = row.get("hrs_left")
                try:
                    hrs_left_float = float(hrs_left_val) if hrs_left_val not in (None, "") else None
                except (TypeError, ValueError):
                    hrs_left_float = None
                if hrs_left_float is not None:
                    if hrs_left_float < 0:
                        hrs_left_display = "Expired"
                    elif hrs_left_float >= 24:
                        hrs_left_display = f"{int(hrs_left_float // 24)}d"
                    else:
                        hrs_left_display = f"{hrs_left_float:.1f}h"
                else:
                    hrs_left_display = "—"
            countdown = _format_countdown(event_time_dt)
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
                "resolution_display": resolution_display,
                "hrs_left_display": hrs_left_display,
                "countdown": countdown,
                "hrs_left_float": hrs_left_float,
            })
    except (IOError, csv.Error):
        return None

    # Hours left filter (show only rows with 0 <= hrs_left <= hours_max)
    if hours_max is not None and hours_max > 0:
        rows = [r for r in rows if r.get("hrs_left_float") is not None and 0 <= r["hrs_left_float"] <= hours_max]

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
    elif sort == "hrs_asc":
        # Soonest to resolve first (null/expired hrs_left last)
        rows.sort(key=lambda r: (r.get("hrs_left_float") if r.get("hrs_left_float") is not None and r.get("hrs_left_float") >= 0 else float("inf"), -_ts_key(r).timestamp()))
    elif sort == "hrs_desc":
        # Latest to resolve first (null hrs_left last)
        rows.sort(key=lambda r: (-(r.get("hrs_left_float") if r.get("hrs_left_float") is not None else float("-inf")), -_ts_key(r).timestamp()))
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


def collect_json_artifact_schema_warnings(data_path: str) -> list[str]:
    """
    If producer JSON has schema_version newer than SUPPORTED_JSON_ARTIFACT_SCHEMA_VERSION,
    return user-facing warning strings. Missing schema_version is treated as legacy (no warning).
    """
    warnings: list[str] = []
    if not data_path or not os.path.isdir(data_path):
        return warnings
    supported = int(SUPPORTED_JSON_ARTIFACT_SCHEMA_VERSION)
    for filename, loader in (
        ("analytics.json", lambda: get_analytics_json(data_path)),
        ("lifecycle.json", lambda: get_lifecycle_json(data_path)),
    ):
        obj = loader()
        if not obj:
            continue
        v = obj.get("schema_version")
        if v is None:
            continue
        try:
            vi = int(v)
        except (TypeError, ValueError):
            warnings.append(f"{filename}: invalid schema_version (expected integer).")
            continue
        if vi > supported:
            warnings.append(
                f"{filename}: schema_version {vi} is newer than this dashboard supports ({supported})."
            )
    return warnings


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



AI_ARTIFACT_SCHEMA_VERSION = 1


def _ai_performance_artifact_path(data_path: str) -> str:
    return os.path.join(data_path, "ai_performance.json")


def _load_ai_performance_artifact(data_path: str) -> Optional[dict]:
    p = _ai_performance_artifact_path(data_path)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def _ai_artifact_stale_wrt_csv(data_path: str, artifact: dict) -> bool:
    """True when alerts_log.csv is newer than the snapshot embedded in the artifact."""
    csv_path = os.path.join(data_path, "alerts_log.csv")
    if not os.path.isfile(csv_path):
        return True
    meta = artifact.get("freshness") or {}
    stored = meta.get("alerts_log_csv_mtime")
    if stored is None:
        return True
    try:
        return os.path.getmtime(csv_path) > float(stored) + 1e-6
    except (OSError, TypeError, ValueError):
        return True


# Phase 3 — live producer diagnostics (aligned with polymarket-alerts core/ai_loop_state.py)
_AI_LOOP_COUNTER_ORDER: tuple[tuple[str, str], ...] = (
    ("ai_candidates_seen", "Candidates seen"),
    ("ai_candidates_screened", "Candidates screened"),
    ("ai_disabled_count", "AI disabled skips"),
    ("ai_no_candidate_count", "No candidate"),
    ("ai_parse_fail_count", "Parse failures"),
    ("ai_timeout_count", "Timeouts"),
    ("ai_error_count", "Other API errors"),
    ("ai_bet_count", "BET verdicts"),
    ("ai_caution_count", "CAUTION verdicts"),
    ("ai_skip_count", "SKIP verdicts"),
    ("ai_hard_block_count", "Hard blocks"),
)


def _load_ai_loop_state_live(data_path: str) -> Optional[dict]:
    """Read ai_loop_state.json from the data directory (Phase 1 producer observability)."""
    p = os.path.join(data_path, "ai_loop_state.json")
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def _producer_counter_rows(counters: object) -> list[dict]:
    if not isinstance(counters, dict):
        return []
    rows: list[dict] = []
    for key, label in _AI_LOOP_COUNTER_ORDER:
        if key not in counters:
            continue
        try:
            val = int(counters[key])
        except (TypeError, ValueError):
            val = counters[key]
        rows.append({"key": key, "label": label, "value": val})
    return rows


def _apply_live_ai_loop_diagnostics(
    data_path: str,
    out: dict,
    artifact_producer: Optional[dict],
) -> None:
    """
    Prefer live ai_loop_state.json for counters/policy (ops truth); fall back to artifact snapshot.
    Sets ai_loop_display_source: live | artifact_snapshot | none.
    """
    live = _load_ai_loop_state_live(data_path)
    if live:
        out["producer_counters"] = live.get("counters")
        out["producer_global_ai_policy"] = live.get("global_ai_policy")
        out["producer_allow_hard_block"] = live.get("allow_hard_block")
        out["producer_last_ai_screen_ts"] = live.get("last_ai_screen_ts")
        out["producer_last_ai_sim_ts"] = live.get("last_ai_sim_ts")
        out["producer_loop_updated_at"] = live.get("updated_at")
        out["producer_loop_schema_version"] = live.get("schema_version")
        lsm = live.get("last_screen_meta")
        out["producer_last_screen_meta"] = lsm if isinstance(lsm, dict) else None
        out["ai_loop_display_source"] = "live"
        out["producer_counter_rows"] = _producer_counter_rows(out.get("producer_counters"))
        return
    if artifact_producer:
        out["producer_counters"] = artifact_producer.get("counters")
        out["producer_global_ai_policy"] = artifact_producer.get("global_ai_policy")
        out["producer_allow_hard_block"] = artifact_producer.get("allow_hard_block")
        out["producer_last_ai_screen_ts"] = artifact_producer.get("last_ai_screen_ts")
        out["producer_last_ai_sim_ts"] = artifact_producer.get("last_ai_sim_ts")
        out["producer_loop_updated_at"] = artifact_producer.get("updated_at")
        out["producer_loop_schema_version"] = None
        lsm = artifact_producer.get("last_screen_meta")
        out["producer_last_screen_meta"] = lsm if isinstance(lsm, dict) else None
        out["ai_loop_display_source"] = "artifact_snapshot"
        out["producer_counter_rows"] = _producer_counter_rows(out.get("producer_counters"))
        return
    out["ai_loop_display_source"] = "none"
    out["producer_counter_rows"] = []
    out["producer_last_screen_meta"] = None


def _sim_lists_from_artifact_sim(sim_section: dict, strategy: Optional[str]) -> tuple[list[dict], list[dict], int]:
    """Deserialize producer sim snapshot; filter by strategy; restore datetime fields."""
    strat = (strategy or "").strip().lower()
    want_all = strat in ("", "all")

    sid = (strategy or "").strip()

    def _ok(r: dict) -> bool:
        if want_all:
            return True
        return (r.get("strategy_id") or "").strip() == sid

    def _ts(val) -> Optional[datetime]:
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            return _parse_iso_datetime(val) or _parse_date(val)
        return None

    open_rows: list[dict] = []
    resolved_rows: list[dict] = []
    for r in sim_section.get("open_list") or []:
        if not isinstance(r, dict) or not _ok(r):
            continue
        row = dict(r)
        row["ts"] = _ts(row.get("ts"))
        open_rows.append(row)
    for r in sim_section.get("resolved_list") or []:
        if not isinstance(r, dict) or not _ok(r):
            continue
        row = dict(r)
        row["resolved_ts"] = _ts(row.get("resolved_ts"))
        resolved_rows.append(row)

    alerts_total = len([x for x in (sim_section.get("open_list") or []) if isinstance(x, dict) and _ok(x)])
    alerts_total += len([x for x in (sim_section.get("resolved_list") or []) if isinstance(x, dict) and _ok(x)])
    return resolved_rows, open_rows, alerts_total


def _finalize_ai_sim_stats_body(
    resolved_rows: list[dict],
    open_rows: list[dict],
    alerts_total: int,
    bankroll: Optional[dict],
    filter: str,
    days: Optional[int],
    sort: str,
    *,
    data_source: str = "csv",
    artifact_exported_at: Optional[str] = None,
    producer_snapshot: Optional[dict] = None,
    data_path: Optional[str] = None,
) -> dict:
    """Shared tail: time window, win/loss filter, sort, chart, display fields."""
    # Date filter
    cutoff = None
    if days is not None and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    if cutoff is not None:
        def _within(r: dict) -> bool:
            t = r.get("resolved_ts") or r.get("ts")
            if not t:
                return True
            t = t.replace(tzinfo=timezone.utc) if isinstance(t, datetime) and t.tzinfo is None else t
            return t >= cutoff  # type: ignore[operator]

        resolved_rows = [r for r in resolved_rows if _within(r)]

    if filter == "wins":
        resolved_rows = [r for r in resolved_rows if r["pnl_usd"] > 0]
    elif filter == "losses":
        resolved_rows = [r for r in resolved_rows if r["pnl_usd"] < 0]

    wins = sum(1 for r in resolved_rows if r["pnl_usd"] > 0)
    losses = sum(1 for r in resolved_rows if r["pnl_usd"] < 0)
    total_pnl = sum(r["pnl_usd"] for r in resolved_rows)

    def _ts_key(x: dict) -> float:
        t = x.get("resolved_ts")
        return t.timestamp() if isinstance(t, datetime) else 0.0

    if sort == "pnl_asc":
        resolved_rows = sorted(resolved_rows, key=lambda x: (x["pnl_usd"], -_ts_key(x)))
    elif sort == "pnl_desc":
        resolved_rows = sorted(resolved_rows, key=lambda x: (-x["pnl_usd"], -_ts_key(x)))
    elif sort == "date_asc":
        resolved_rows = sorted(resolved_rows, key=lambda x: (_ts_key(x), x["pnl_usd"]))
    else:
        resolved_rows = sorted(resolved_rows, key=lambda x: (-_ts_key(x), x["pnl_usd"]))

    def _open_ts(x: dict) -> float:
        t = x.get("ts")
        return t.timestamp() if isinstance(t, datetime) else 0.0

    open_rows = sorted(open_rows, key=_open_ts, reverse=True)

    chart_rows = sorted([r for r in resolved_rows if r.get("resolved_ts")], key=lambda x: x["resolved_ts"])  # type: ignore[arg-type]
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    chart_data: list[dict] = []
    for r in chart_rows:
        cumulative += r["pnl_usd"]
        peak = max(peak, cumulative)
        dd = cumulative - peak
        if dd < max_drawdown:
            max_drawdown = dd
        rt = r.get("resolved_ts")
        if isinstance(rt, datetime):
            chart_data.append({"date": rt.strftime("%Y-%m-%d"), "pnl": round(cumulative, 2)})

    for r in resolved_rows:
        r["pnl_display"] = f"${r['pnl_usd']:.2f}"
        r["bet_size_display"] = format_compact_usd(r["bet_size_usd"] or 0.0)
        r["resolved_ts_display"] = format_ts_display(r.get("resolved_ts"))
    for r in open_rows:
        r["bet_size_display"] = format_compact_usd(r["bet_size_usd"] or 0.0)
        r["ts_display"] = format_ts_display(r.get("ts"))

    out: dict = {
        "alerts_total": alerts_total,
        "open": len(open_rows),
        "resolved": len(resolved_rows),
        "wins": wins,
        "losses": losses,
        "total_pnl": round(total_pnl, 2),
        "total_pnl_display": f"${total_pnl:.2f}",
        "resolved_list": resolved_rows,
        "open_list": open_rows,
        "chart_data": chart_data,
        "max_drawdown": round(max_drawdown, 2),
        "max_drawdown_display": f"${max_drawdown:.2f}",
        "bankroll": bankroll,
        "data_source": data_source,
        "artifact_exported_at": artifact_exported_at,
    }
    out["recent_open_list"] = list(open_rows[:25])
    if data_path:
        _apply_live_ai_loop_diagnostics(data_path, out, producer_snapshot if producer_snapshot else None)
    return out


def get_ai_performance(data_path: str, strategy: Optional[str] = None) -> dict:
    """
    Analyse AI screener accuracy by joining ai_verdict/ai_confidence
    against actual_result on resolved rows.

    Accuracy semantics (direction-based, not pnl-sign):
      BET    = correct if actual_result == "YES" (bet would have won)
      SKIP   = correct if actual_result == "NO"  (avoided a loss)
      CAUTION = same direction logic as BET (informational)

    For SKIP rows pnl_usd is always 0.00 (no bet placed), so pnl-sign
    is broken. Counterfactual P/L is estimated using _CF_STANDARD_BET
    as a proxy for the unknown blocked bet size.
    """
    empty = {
        "has_data": False,
        "accuracy_tiers": [],
        "blocked_rows": [],
        "blocked_rows_full_count": 0,
        "total_screened": 0,
        "total_blocked": 0,
        "overall_accuracy": None,
        "baseline_loss_rate": None,
        "cf_standard_bet": _CF_STANDARD_BET,
        "data_source": "none",
        "lift_metrics": {
            "false_block_rate_pct": None,
            "loss_avoided_rate_pct": None,
            "blocked_judged_count": 0,
            "counterfactual_blocked_pnl_est": None,
            "baseline_loss_rate_pct": None,
            "skip_tier_lift_pp": None,
        },
    }
    if not data_path or not os.path.isdir(data_path):
        return empty

    art = _load_ai_performance_artifact(data_path)
    if (
        art
        and int(art.get("schema_version") or 0) == AI_ARTIFACT_SCHEMA_VERSION
        and not _ai_artifact_stale_wrt_csv(data_path, art)
        and (strategy or "all").strip().lower() == "all"
    ):
        perf = art.get("performance")
        if isinstance(perf, dict) and perf:
            out = copy.deepcopy(perf)
            out.setdefault("cf_standard_bet", _CF_STANDARD_BET)
            out["data_source"] = "artifact"
            out["artifact_exported_at"] = art.get("exported_at")
            prod = art.get("producer") or {}
            _apply_live_ai_loop_diagnostics(data_path, out, prod if prod else None)
            return out

    csv_path = os.path.join(data_path, "alerts_log.csv")
    result = _read_csv_cached(csv_path)
    if result is None:
        out = copy.deepcopy(empty)
        _apply_live_ai_loop_diagnostics(data_path, out, None)
        return out
    _, rows = result
    if not rows:
        out = copy.deepcopy(empty)
        _apply_live_ai_loop_diagnostics(data_path, out, None)
        return out
    if strategy and strategy.strip().lower() != "all":
        rows = [r for r in rows if (r.get("strategy_id") or "").strip() == strategy.strip()]

    # Baseline loss rate: fraction of sent rows that resolved NO (for lift comparison).
    sent_resolved = [
        r for r in rows
        if (r.get("status") or "").strip().lower() == "sent"
        and (r.get("actual_result") or "").strip().upper() in ("YES", "NO")
    ]
    baseline_loss_rate: float | None = None
    if sent_resolved:
        losses = sum(1 for r in sent_resolved if r["actual_result"].strip().upper() == "NO")
        baseline_loss_rate = round(losses / len(sent_resolved) * 100, 1)

    tiers: dict[tuple, dict] = defaultdict(lambda: {
        "resolved": 0, "correct": 0, "wrong": 0,
        "pnl": 0.0, "cf_pnl_saved": 0.0,
    })
    blocked_rows = []
    total_screened = 0

    for row in rows:
        status = (row.get("status") or "").strip().lower()
        ai_verdict = (row.get("ai_verdict") or "").strip().upper()
        ai_confidence = (row.get("ai_confidence") or "").strip().capitalize()
        ai_red_flags = (row.get("ai_red_flags") or "").strip()

        if status == "blocked_ai_screen":
            actual_r = (row.get("actual_result") or "").strip().upper()
            entry_price = _parse_float(row.get("best_ask") or row.get("yes_price"))
            if actual_r == "NO":
                outcome_verdict = "correct"
                cf_pnl_est: float | None = _CF_STANDARD_BET
            elif actual_r == "YES":
                outcome_verdict = "wrong"
                cf_pnl_est = -(_CF_STANDARD_BET * (1.0 / entry_price - 1.0)) if entry_price > 0 else 0.0
            else:
                outcome_verdict = "pending"
                cf_pnl_est = None
            blocked_rows.append({
                "ts": (row.get("ts") or "")[:16],
                "question": (row.get("question") or "")[:80],
                "sport": row.get("sport") or "",
                "market_type": row.get("market_type") or "",
                "ai_confidence": ai_confidence,
                "red_flags": [f.strip() for f in ai_red_flags.split("|") if f.strip()],
                "reasoning": (row.get("primary_block_reason") or "").replace("AI_SKIP_HIGH: ", ""),
                "link": (row.get("link") or "").strip(),
                "actual_result": actual_r,
                "pnl_usd": _parse_float(row.get("pnl_usd")),  # always 0.00, kept for compat
                "outcome_verdict": outcome_verdict,
                "cf_pnl_est": round(cf_pnl_est, 2) if cf_pnl_est is not None else None,
                "entry_price": round(entry_price, 4) if entry_price else None,
            })

        if not ai_verdict:
            continue
        total_screened += 1

        actual = (row.get("actual_result") or "").strip().upper()
        is_resolved = _parse_bool(row.get("resolved")) or actual in ("YES", "NO")
        if not is_resolved:
            continue

        tier_key = (ai_verdict, ai_confidence)
        tiers[tier_key]["resolved"] += 1

        if ai_verdict == "SKIP":
            entry = _parse_float(row.get("best_ask") or row.get("yes_price"))
            if actual == "NO":
                tiers[tier_key]["correct"] += 1
                tiers[tier_key]["cf_pnl_saved"] += _CF_STANDARD_BET
            elif actual == "YES":
                tiers[tier_key]["wrong"] += 1
                opp = _CF_STANDARD_BET * (1.0 / entry - 1.0) if entry > 0 else 0.0
                tiers[tier_key]["cf_pnl_saved"] -= opp
        else:  # BET / CAUTION
            if actual == "YES":
                tiers[tier_key]["correct"] += 1
            elif actual == "NO":
                tiers[tier_key]["wrong"] += 1
            tiers[tier_key]["pnl"] += _parse_float(row.get("pnl_usd"))

    order = {"BET": 0, "CAUTION": 1, "SKIP": 2}
    conf_order = {"High": 0, "Medium": 1, "Low": 2}
    accuracy_tiers = []
    for (verdict, confidence), stats in sorted(
        tiers.items(),
        key=lambda x: (order.get(x[0][0], 9), conf_order.get(x[0][1], 9))
    ):
        resolved = stats["resolved"]
        correct = stats["correct"]
        wrong = stats["wrong"]
        pending = resolved - correct - wrong
        judged = correct + wrong
        accuracy_pct: float | None = round(correct / judged * 100, 1) if judged > 0 else None
        tier_dict: dict = {
            "verdict": verdict,
            "confidence": confidence,
            "resolved": resolved,
            "correct": correct,
            "wrong": wrong,
            "pending": pending,
            "accuracy_pct": accuracy_pct,
            "pnl": round(stats["pnl"], 2),
            "pnl_display": f"${stats['pnl']:.2f}",
        }
        if verdict == "SKIP":
            cf = stats["cf_pnl_saved"]
            tier_dict["cf_pnl_saved"] = round(cf, 2)
            tier_dict["cf_pnl_saved_display"] = f"${cf:+.2f} est."
            tier_dict["lift"] = (
                round(accuracy_pct - baseline_loss_rate, 1)
                if (accuracy_pct is not None and baseline_loss_rate is not None)
                else None
            )
        accuracy_tiers.append(tier_dict)

    total_judged = sum(t["correct"] + t["wrong"] for t in accuracy_tiers)
    total_correct = sum(t["correct"] for t in accuracy_tiers)
    overall = round(total_correct / total_judged * 100, 1) if total_judged > 0 else None

    blocked_rows.sort(key=lambda x: x["ts"], reverse=True)

    judged_blocked = [b for b in blocked_rows if b.get("outcome_verdict") in ("correct", "wrong")]
    fb_wrong = sum(1 for b in judged_blocked if b["outcome_verdict"] == "wrong")
    fb_correct = sum(1 for b in judged_blocked if b["outcome_verdict"] == "correct")
    fb_judged = fb_wrong + fb_correct
    false_block_rate = round(fb_wrong / fb_judged * 100, 1) if fb_judged else None
    loss_avoided_rate = round(fb_correct / fb_judged * 100, 1) if fb_judged else None
    cf_blocked_sum = sum((b.get("cf_pnl_est") or 0.0) for b in judged_blocked)
    skip_lift_pp = None
    for t in accuracy_tiers:
        if t.get("verdict") == "SKIP" and t.get("confidence") == "High":
            skip_lift_pp = t.get("lift")
            break

    out = {
        "has_data": bool(accuracy_tiers or blocked_rows),
        "accuracy_tiers": accuracy_tiers,
        "blocked_rows": blocked_rows[:100],
        "blocked_rows_full_count": len(blocked_rows),
        "total_screened": total_screened,
        "total_blocked": len(blocked_rows),
        "overall_accuracy": overall,
        "baseline_loss_rate": baseline_loss_rate,
        "cf_standard_bet": _CF_STANDARD_BET,
        "data_source": "csv",
        "lift_metrics": {
            "false_block_rate_pct": false_block_rate,
            "loss_avoided_rate_pct": loss_avoided_rate,
            "blocked_judged_count": fb_judged,
            "counterfactual_blocked_pnl_est": round(cf_blocked_sum, 2) if judged_blocked else None,
            "baseline_loss_rate_pct": baseline_loss_rate,
            "skip_tier_lift_pp": skip_lift_pp,
        },
    }
    _apply_live_ai_loop_diagnostics(data_path, out, None)
    return out


def get_ai_sim_stats(
    data_path: str,
    filter: str = "all",
    days: Optional[int] = None,
    sort: str = "date_desc",
    strategy: Optional[str] = None,
    safe_scope: str = "all_tracked",
) -> Optional[dict]:
    """
    Prefer ai_performance.json when fresh; else read alerts_log.csv.
    Always reads ai_sim_bankroll.json for live bankroll display.
    """
    empty: dict = {
        "alerts_total": 0, "open": 0, "resolved": 0,
        "wins": 0, "losses": 0, "total_pnl": 0.0,
        "total_pnl_display": "$0.00", "resolved_list": [],
        "open_list": [], "chart_data": [],
        "max_drawdown": 0, "max_drawdown_display": "$0.00",
        "bankroll": None,
        "data_source": "none",
        "artifact_exported_at": None,
        "recent_open_list": [],
    }
    if not data_path or not os.path.isdir(data_path):
        return None

    bankroll_path = os.path.join(data_path, "ai_sim_bankroll.json")
    bankroll = None
    if os.path.isfile(bankroll_path):
        try:
            with open(bankroll_path, "r", encoding="utf-8") as f:
                bankroll = json.load(f)
        except Exception:
            bankroll = None

    art = _load_ai_performance_artifact(data_path)
    if (
        art
        and int(art.get("schema_version") or 0) == AI_ARTIFACT_SCHEMA_VERSION
        and not _ai_artifact_stale_wrt_csv(data_path, art)
    ):
        sim_sec = art.get("sim")
        if isinstance(sim_sec, dict) and (sim_sec.get("resolved_list") is not None or sim_sec.get("open_list") is not None):
            resolved_rows, open_rows, alerts_total = _sim_lists_from_artifact_sim(sim_sec, strategy)
            if safe_scope == "safe_only":
                allowed_sports = _safe_execution_sports()
                resolved_rows = [r for r in resolved_rows if (r.get("sport") or "").strip().lower() in allowed_sports]
                open_rows = [r for r in open_rows if (r.get("sport") or "").strip().lower() in allowed_sports]
                alerts_total = len(resolved_rows) + len(open_rows)
            prod = art.get("producer") or {}
            return _finalize_ai_sim_stats_body(
                resolved_rows,
                open_rows,
                alerts_total,
                bankroll,
                filter,
                days,
                sort,
                data_source="artifact",
                artifact_exported_at=art.get("exported_at"),
                producer_snapshot=prod if isinstance(prod, dict) else None,
                data_path=data_path,
            )

    csv_path = os.path.join(data_path, "alerts_log.csv")
    if not os.path.isfile(csv_path):
        out = {**empty, "bankroll": bankroll}
        _apply_live_ai_loop_diagnostics(data_path, out, None)
        return out

    result = _read_csv_cached(csv_path)
    if result is None:
        out = {**empty, "bankroll": bankroll}
        _apply_live_ai_loop_diagnostics(data_path, out, None)
        return out
    _, all_rows = result
    if strategy and strategy.strip().lower() != "all":
        all_rows = [r for r in all_rows if (r.get("strategy_id") or "").strip() == strategy.strip()]

    sim_rows = [r for r in all_rows if (r.get("status") or "").strip().lower() == "ai_sim"]
    if safe_scope == "safe_only":
        allowed_sports = _safe_execution_sports()
        sim_rows = [r for r in sim_rows if (r.get("sport") or "").strip().lower() in allowed_sports]

    resolved_rows = []
    open_rows = []
    alerts_total = 0

    for row in sim_rows:
        alerts_total += 1
        actual_result = (row.get("actual_result") or "").strip().upper()
        is_resolved = _parse_bool(row.get("resolved")) or actual_result in ("YES", "NO")
        pnl = _parse_float(row.get("pnl_usd"))
        question = row.get("question") or ""
        link = (row.get("link") or "").strip()
        label = _get_display_label(question)
        resolved_ts = _parse_date(row.get("resolved_ts") or row.get("ts"))
        ts = _parse_date(row.get("ts"))
        bet_size = _parse_float(row.get("bet_size_usd") or row.get("cost_usd") or 0.0)
        ai_verdict = (row.get("ai_verdict") or "").strip().upper()
        ai_confidence = (row.get("ai_confidence") or "").strip().capitalize()
        ai_red_flags = [f.strip() for f in (row.get("ai_red_flags") or "").split("|") if f.strip()]
        ai_size_mult = row.get("ai_size_mult") or ""
        sport = row.get("sport") or ""

        base: dict = {
            "question": label, "actual_result": actual_result or "—",
            "pnl_usd": pnl, "link": link if link.startswith("http") else "",
            "bet_size_usd": bet_size, "ai_verdict": ai_verdict,
            "ai_confidence": ai_confidence, "ai_red_flags": ai_red_flags,
            "ai_size_mult": ai_size_mult, "sport": sport,
            "strategy_id": row.get("strategy_id") or "",
            "rationale": {
                "gamma": _parse_float(row.get("gamma")),
                "best_ask": _parse_float(row.get("best_ask")),
                "effective": _parse_float(row.get("effective")),
                "edge": _parse_float(row.get("edge")),
            },
        }

        if is_resolved:
            resolved_rows.append({**base, "resolved_ts": resolved_ts})
        else:
            open_rows.append({**base, "ts": ts})

    return _finalize_ai_sim_stats_body(
        resolved_rows,
        open_rows,
        alerts_total,
        bankroll,
        filter,
        days,
        sort,
        data_source="csv",
        artifact_exported_at=None,
        producer_snapshot=None,
        data_path=data_path,
    )


def get_mirror_portfolio_json(data_path: str) -> Optional[dict]:
    """
    Load mirror_portfolio.json from polymarket-alerts (from analytics/mirror_portfolio_export.py).
    Read-only mirror of a wallet's public trades: ledger, open positions, resolution_events, anomalies.
    """
    if not data_path or not os.path.isdir(data_path):
        return None
    import json

    path = os.path.join(data_path, "mirror_portfolio.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return None


def get_mirror_portfolio_file_age(data_path: str) -> Optional[str]:
    """Return human-readable age of mirror_portfolio.json, or None if missing."""
    return get_file_age(data_path, "mirror_portfolio.json")


MIRROR_POLL_GROUP_STANDARD = "standard"
MIRROR_POLL_GROUP_FAST = "fast"
# (value, label) for Mirror alerts UI
MIRROR_POLL_GROUPS = (
    (MIRROR_POLL_GROUP_STANDARD, "Standard (e.g. every 5 min)"),
    (MIRROR_POLL_GROUP_FAST, "Fast (e.g. every 1 min)"),
)

MIRROR_WATCH_MAX_WALLETS = 20


def normalize_mirror_poll_group(raw) -> str:
    s = str(raw or "").strip().lower()
    if s == MIRROR_POLL_GROUP_FAST:
        return MIRROR_POLL_GROUP_FAST
    return MIRROR_POLL_GROUP_STANDARD


def get_mirror_watch_config(data_path: str) -> Optional[dict]:
    """
    Load mirror_watch_config.json (multi-wallet Telegram watch list for jobs/mirror_watch.py).
    Returns { version, wallets: [{ id, address, label, telegram_enabled, poll_group }, ...] } or empty wallets.
    """
    if not data_path or not os.path.isdir(data_path):
        return None
    import json

    path = os.path.join(data_path, "mirror_watch_config.json")
    if not os.path.isfile(path):
        return {"version": 1, "wallets": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError):
        return {"version": 1, "wallets": []}
    if not isinstance(data, dict):
        return {"version": 1, "wallets": []}
    wallets = data.get("wallets")
    if not isinstance(wallets, list):
        data["wallets"] = []
        return data
    for w in wallets:
        if isinstance(w, dict):
            w["poll_group"] = normalize_mirror_poll_group(w.get("poll_group"))
    return data


def save_mirror_watch_config(data_path: str, cfg: dict) -> tuple[bool, str]:
    """
    Write mirror_watch_config.json. Validates at most MIRROR_WATCH_MAX_WALLETS unique 0x addresses.
    Preserves min_notional_usd from disk or explicit cfg when present.
    Returns (ok, error_message).
    """
    import json
    import re
    import uuid

    if not data_path or not os.path.isdir(data_path):
        return False, "Invalid data path"
    wallets_in = cfg.get("wallets") if isinstance(cfg, dict) else None
    if not isinstance(wallets_in, list):
        return False, "Invalid wallets list"
    addr_re = re.compile(r"^0x[a-fA-F0-9]{40}$")
    seen: set[str] = set()
    out: list[dict] = []
    for w in wallets_in[:MIRROR_WATCH_MAX_WALLETS]:
        if not isinstance(w, dict):
            continue
        addr = (w.get("address") or "").strip()
        if not addr_re.match(addr):
            continue
        addr = addr.lower()
        if addr in seen:
            continue
        seen.add(addr)
        wid = str(w.get("id") or "").strip() or uuid.uuid4().hex[:12]
        label = str(w.get("label") or "").strip() or addr[:10] + "…"
        tg = w.get("telegram_enabled", True)
        if not isinstance(tg, bool):
            tg = str(tg).lower() in ("1", "true", "yes", "on")
        pg = normalize_mirror_poll_group(w.get("poll_group"))
        out.append(
            {
                "id": wid[:32],
                "address": addr,
                "label": label[:80],
                "telegram_enabled": tg,
                "poll_group": pg,
            }
        )
    path = os.path.join(data_path, "mirror_watch_config.json")
    payload: dict = {"version": 1, "wallets": out}
    existing_mn: Optional[float] = None
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                old = json.load(f)
            if isinstance(old, dict) and "min_notional_usd" in old:
                try:
                    existing_mn = max(0.0, float(old["min_notional_usd"]))
                except (TypeError, ValueError):
                    pass
        except (json.JSONDecodeError, OSError):
            pass
    if isinstance(cfg, dict) and "min_notional_usd" in cfg:
        try:
            payload["min_notional_usd"] = max(0.0, float(cfg["min_notional_usd"]))
        except (TypeError, ValueError):
            if existing_mn is not None:
                payload["min_notional_usd"] = existing_mn
    elif existing_mn is not None:
        payload["min_notional_usd"] = existing_mn
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except OSError as e:
        return False, str(e)
    return True, ""


def get_file_age(data_path: str, filename: str) -> Optional[str]:
    """Return human-readable age of a file under data_path, or None if missing."""
    if not data_path or not os.path.isdir(data_path):
        return None
    path = os.path.join(data_path, filename)
    if not os.path.isfile(path):
        return None
    try:
        return _format_file_age(os.path.getmtime(path))
    except OSError:
        return None
