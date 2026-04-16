"""
Health and freshness helpers for Polymarket integration.

These helpers are intentionally small and focused so they can be probed by:
- internal admin views
- external monitoring (via JSON endpoints)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

from .polymarket import (
    is_polymarket_configured,
    get_file_age,
    get_analytics_file_age,
    get_lifecycle_file_age,
    validate_alerts_log_schema,
    get_last_loop_time,
)


@dataclass
class PolymarketFreshness:
    """Human-readable freshness for core Polymarket artifacts."""

    alerts_log_age: Optional[str]
    open_positions_age: Optional[str]
    execution_log_age: Optional[str]
    debug_candidates_age: Optional[str]
    analytics_age: Optional[str]
    lifecycle_age: Optional[str]
    ai_performance_age: Optional[str]
    last_loop_run: Optional[str]


@dataclass
class PolymarketHealth:
    """Overall health snapshot suitable for JSON health endpoints."""

    configured: bool
    alerts_schema_ok: bool
    alerts_schema_error: Optional[str]
    freshness: PolymarketFreshness

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Flatten nested dataclass to simple dict for JSON responses
        freshness = d.pop("freshness", {}) or {}
        d.update({"freshness": freshness})
        return d


def _get_data_path() -> str:
    """
    Local import of _get_data_path from routes.polymarket to avoid circular imports.

    This keeps the routing layer and health helpers loosely coupled while still
    using a single source of truth for POLYMARKET_DATA_PATH resolution.
    """
    from app.routes.polymarket import _get_data_path as _route_get_data_path  # type: ignore

    return _route_get_data_path()


def get_polymarket_freshness() -> PolymarketFreshness:
    """
    Return human-readable age for the key Polymarket data files.

    All values are strings like "just now", "5 min ago", "2 days ago", or None
    when the file is missing or the integration is not configured.
    """
    if not is_polymarket_configured():
        return PolymarketFreshness(
            alerts_log_age=None,
            open_positions_age=None,
            execution_log_age=None,
            debug_candidates_age=None,
            analytics_age=None,
            lifecycle_age=None,
            ai_performance_age=None,
            last_loop_run=None,
        )

    data_path = _get_data_path()

    alerts_age = get_file_age(data_path, "alerts_log.csv")
    open_positions_age = get_file_age(data_path, "open_positions.csv")
    execution_log_age = get_file_age(data_path, "execution_log.csv")
    debug_candidates_age = get_file_age(data_path, "debug_candidates.csv")

    analytics_age = get_analytics_file_age(data_path)
    lifecycle_age = get_lifecycle_file_age(data_path)
    ai_performance_age = get_file_age(data_path, "ai_performance.json")
    last_loop = get_last_loop_time(data_path)

    return PolymarketFreshness(
        alerts_log_age=alerts_age,
        open_positions_age=open_positions_age,
        execution_log_age=execution_log_age,
        debug_candidates_age=debug_candidates_age,
        analytics_age=analytics_age,
        lifecycle_age=lifecycle_age,
        ai_performance_age=ai_performance_age,
        last_loop_run=last_loop,
    )


def get_polymarket_health() -> PolymarketHealth:
    """
    Best-practice, low-cardinality health summary for monitoring.

    - configured: whether POLYMARKET_DATA_PATH is set and exists
    - alerts_schema_ok: True when alerts_log.csv matches the expected schema
    - alerts_schema_error: short explanation when schema check fails
    - freshness: human-readable ages for core files
    """
    configured = is_polymarket_configured()
    alerts_ok = True
    alerts_error: Optional[str] = None

    if configured:
        data_path = _get_data_path()
        alerts_ok, alerts_error = validate_alerts_log_schema(data_path)

    freshness = get_polymarket_freshness()
    return PolymarketHealth(
        configured=configured,
        alerts_schema_ok=alerts_ok,
        alerts_schema_error=alerts_error,
        freshness=freshness,
    )

