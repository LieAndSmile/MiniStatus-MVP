from flask import Blueprint, g, render_template, request, send_file, redirect, session, url_for, flash, jsonify
from functools import wraps
import os
import re
import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

from app.utils.polymarket import (
    get_polymarket_stats,
    is_polymarket_configured,
    get_last_loop_time,
    get_run_stats_log,
    get_loss_breakdown,
    get_loss_breakdown_buckets,
    get_loss_trend_by_category,
    get_debug_candidates,
    get_open_positions,
    get_risky_positions,
    get_risky_criteria,
    get_risky_historical_performance,
    get_near_risky_positions,
    get_interesting_ids,
    toggle_interesting,
    get_exposure_summary,
    validate_alerts_log_schema,
    format_compact_usd,
    build_pagination,
    get_analytics_json,
    get_lifecycle_json,
    get_analytics_file_age,
    get_lifecycle_file_age,
    get_file_age,
    get_strategy_options_for_nav,
    get_strategy_options_grouped,
    get_alerts_status_summary,
    get_recent_decisions,
    get_bankroll_status,
    get_strategy_summary,
    get_ai_performance,
    get_ai_sim_stats,
    get_strategy_scorecard,
    get_mirror_portfolio_json,
    get_mirror_portfolio_file_age,
    get_mirror_watch_config,
    save_mirror_watch_config,
    collect_json_artifact_schema_warnings,
    MIRROR_WATCH_MAX_WALLETS,
    MIRROR_POLL_GROUPS,
    normalize_mirror_poll_group,
    SORT_OPTIONS,
    DEBUG_SORT_OPTIONS,
    LOOP_HOURS_MAX_PRESETS,
    POSITIONS_SORT_OPTIONS,
    POSITIONS_EXPIRY_FILTERS,
    STRATEGY_OPTIONS,
    STRATEGY_MODE,
    STRATEGY_LABELS,
)
from app.utils.polymarket_health import get_polymarket_health, get_polymarket_freshness
from app.utils.data_quality import get_data_quality_flags
from app.utils.decorators import admin_required

polymarket_bp = Blueprint("polymarket", __name__, url_prefix="/polymarket")

# Phase 5 Chunk 5a: persist safe-scope choice across Polymarket pages (session-backed).
POLYMARKET_SAFE_SCOPE_SESSION_KEY = "polymarket_safe_scope"


@polymarket_bp.before_request
def _apply_polymarket_safe_scope():
    """Set ``g.polymarket_safe_scope`` and update session when ``?safe_scope=`` is present."""
    raw = request.args.get("safe_scope")
    if raw is not None and str(raw).strip() != "":
        s = str(raw).strip().lower()
        if s in ("safe_only", "all_tracked"):
            session[POLYMARKET_SAFE_SCOPE_SESSION_KEY] = s
            g.polymarket_safe_scope = s
        else:
            g.polymarket_safe_scope = "safe_only"
    else:
        g.polymarket_safe_scope = session.get(POLYMARKET_SAFE_SCOPE_SESSION_KEY, "safe_only")


def _effective_polymarket_safe_scope() -> str:
    return getattr(g, "polymarket_safe_scope", "safe_only")


_MIRROR_WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _normalize_mirror_wallet(s: str):
    """Return checksummed lowercase 0x address or None."""
    if not s or not isinstance(s, str):
        return None
    w = s.strip()
    if _MIRROR_WALLET_RE.match(w):
        return w.lower()
    return None


def _parse_mirror_days(s: str, default: str = "365") -> str:
    try:
        n = int((s or "").strip() or default)
        return str(max(1, min(3650, n)))
    except (TypeError, ValueError):
        return default


PER_PAGE = 50
DEBUG_PER_PAGE = 100

# Top horizontal nav: ≤4 primary tabs (Phase 5 Chunk 5b). Secondary tools live under /polymarket/ops.
POLYMARKET_SECTIONS = [
    ("portfolio", "Live", "polymarket.polymarket_portfolio"),
    ("scorecard", "Scorecard", "polymarket.polymarket_scorecard"),
    ("ai-simulation", "AI Simulation", "polymarket.polymarket_ai_simulation"),
    ("ops", "Ops", "polymarket.polymarket_ops"),
]

# Routes that highlight the "Ops" tab in the four-item nav (and sidebar).
POLYMARKET_OPS_ENDPOINTS = frozenset(
    {
        "polymarket.polymarket_ops",
        "polymarket.polymarket_positions",
        "polymarket.polymarket_risky",
        "polymarket.polymarket_loss_lab",
        "polymarket.polymarket_analytics",
        "polymarket.polymarket_lifecycle",
        "polymarket.polymarket_loop",
        "polymarket.polymarket_ai_performance",
        "polymarket.polymarket_mirror_portfolio",
        "polymarket.polymarket_mirror_alerts",
    }
)


def _polymarket_configured_required(active_section: str):
    """Decorator: render not-configured template if Polymarket data path is not set."""
    def decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            if not is_polymarket_configured():
                return render_template(
                    "polymarket.html",
                    configured=False,
                    stats=None,
                    polymarket_sections=POLYMARKET_SECTIONS,
                    active_section=active_section,
                )
            return f(*args, **kwargs)
        return inner
    return decorator


def _get_data_path():
    """Return POLYMARKET_DATA_PATH or empty string. Call only when configured."""
    return os.getenv("POLYMARKET_DATA_PATH", "").strip()


def _polymarket_freshness_context():
    """Artifact ages for the Polymarket nav strip (same data as /polymarket/freshness JSON)."""
    ctx: dict = {"polymarket_freshness": get_polymarket_freshness()}
    if is_polymarket_configured():
        dp = _get_data_path()
        ctx["polymarket_schema_warnings"] = collect_json_artifact_schema_warnings(dp) if dp else []
    else:
        ctx["polymarket_schema_warnings"] = []
    return ctx


def _parse_scorecard_days():
    """Optional ``days`` query param for scorecard; None means all time."""
    raw = (request.args.get("days") or "").strip().lower()
    if not raw or raw == "all":
        return None
    try:
        d = int(raw)
        return d if d > 0 else None
    except (TypeError, ValueError):
        return None


def _parse_scorecard_days_display() -> str:
    """UI state for scorecard time filter: 'all' | '7' | '30'."""
    raw = (request.args.get("days") or "").strip().lower()
    if not raw or raw == "all":
        return "all"
    if raw in ("7", "30"):
        return raw
    try:
        d = int(raw)
        if d == 7:
            return "7"
        if d == 30:
            return "30"
    except (TypeError, ValueError):
        pass
    return "all"


_SCORECARD_SORT_KEYS = (
    "pnl",
    "strategy",
    "sent",
    "resolved",
    "wins",
    "losses",
    "win_rate",
    "roi",
    "last_sent",
)


def _sort_scorecard_rows(rows: list[dict], sort_col: str, order: str) -> list[dict]:
    """Sort a copy of scorecard rows for HTML table (default: pnl desc)."""
    if sort_col not in _SCORECARD_SORT_KEYS:
        sort_col = "pnl"
    reverse = order == "desc"
    if sort_col == "pnl":
        key = lambda r: float(r.get("realized_pnl_usd") or 0)
    elif sort_col == "strategy":
        key = lambda r: (r.get("strategy_id") or "").lower()
    elif sort_col == "sent":
        key = lambda r: int(r.get("sent") or 0)
    elif sort_col == "resolved":
        key = lambda r: int(r.get("resolved") or 0)
    elif sort_col == "wins":
        key = lambda r: int(r.get("wins") or 0)
    elif sort_col == "losses":
        key = lambda r: int(r.get("losses") or 0)
    elif sort_col == "win_rate":
        key = lambda r: float(r.get("win_rate") or 0)
    elif sort_col == "roi":
        key = lambda r: float(r.get("roi_pct") or 0)
    else:  # last_sent
        key = lambda r: (r.get("last_sent_ts") or "")

    out = list(rows)
    out.sort(key=key, reverse=reverse)
    return out


def _scorecard_sort_href(
    col: str,
    *,
    safe_scope: str,
    days_disp: str,
    sort_col: str,
    order: str,
) -> str:
    """URL for table header: same column toggles order; new column uses default order."""
    if col == sort_col:
        next_order = "asc" if order == "desc" else "desc"
    else:
        next_order = "asc" if col in ("strategy", "last_sent") else "desc"
    q_days = days_disp if days_disp != "all" else "all"
    return url_for(
        "polymarket.polymarket_scorecard",
        format="html",
        safe_scope=safe_scope,
        days=q_days,
        sort=col,
        order=next_order,
    )


def _parse_filter_days():
    """Parse filter and days from request args."""
    filter_val = request.args.get("filter", "all")
    if filter_val not in ("all", "wins", "losses"):
        filter_val = "all"
    days_val = request.args.get("days", "all")
    days = None
    if days_val != "all":
        try:
            days = int(days_val)
            if days <= 0:
                days = None
        except ValueError:
            days = None
    return filter_val, days_val, days


def _pagination_params():
    """Build dict of filter/days/page for URL query strings."""
    filter_val, days_val, days = _parse_filter_days()
    page = max(1, int(request.args.get("page", 1) or 1))
    return {"filter": filter_val, "days": days_val or "all", "page": page}


def _get_strategy(allowed=None):
    """Return strategy from request (v3).

    - ``strategy=all`` or missing/empty → ``None`` (no filter: show all strategy_id values in CSV).
    - Known ``strategy_id`` → that id (Portfolio/P/L filtered to that strategy only).
    - Unknown id → ``None`` (safe fallback).

    Legacy rows often use ``safe_fast`` while new cohorts use ``safe_same_day_core`` / ``safe_1to2d_core``;
    defaulting to "first active" made Portfolio look empty when those IDs had no sent rows yet.
    """
    s = (request.args.get("strategy") or "").strip()
    options = allowed if allowed is not None else STRATEGY_OPTIONS
    if not s or s.lower() == "all":
        return None
    if s in options:
        return s
    return None


# ── Health & freshness (admin) ─────────────────────────────────────────────────
@polymarket_bp.route("/health")
@admin_required
def polymarket_health():
    """
    JSON health endpoint for Polymarket integration.

    Intended for external monitoring and quick diagnostics:
    - 200 OK with current health snapshot (even when misconfigured)
    - low-cardinality, human-readable fields only
    """
    health = get_polymarket_health()
    return jsonify(health.to_dict())


@polymarket_bp.route("/freshness")
@admin_required
def polymarket_freshness():
    """
    JSON freshness endpoint with last-updated ages for key files.

    Useful for probes that only care about staleness thresholds, e.g.:
    - alerts_log.csv older than N minutes
    - open_positions.csv older than N minutes
    """
    freshness = get_polymarket_freshness()
    dp = _get_data_path() if is_polymarket_configured() else ""
    schema_warnings = collect_json_artifact_schema_warnings(dp) if dp else []
    return jsonify(
        {
            "configured": is_polymarket_configured(),
            "freshness": {
                "alerts_log_age": freshness.alerts_log_age,
                "open_positions_age": freshness.open_positions_age,
                "execution_log_age": freshness.execution_log_age,
                "debug_candidates_age": freshness.debug_candidates_age,
                "analytics_age": freshness.analytics_age,
                "lifecycle_age": freshness.lifecycle_age,
                "ai_performance_age": freshness.ai_performance_age,
                "last_loop_run": freshness.last_loop_run,
            },
            "schema_warnings": schema_warnings,
        }
    )


# ── Index & portfolio ─────────────────────────────────────────────────────────
@polymarket_bp.route("")
@polymarket_bp.route("/")
@admin_required
def polymarket_index():
    """Redirect /polymarket to /polymarket/portfolio (default landing)."""
    return redirect(url_for("polymarket.polymarket_portfolio"))


# ── Ops hub (secondary tools) ─────────────────────────────────────────────────
@polymarket_bp.route("/ops")
@admin_required
@_polymarket_configured_required("ops")
def polymarket_ops():
    """Hub for Open Positions, Analytics, mirrors, dev tools — not top-level nav items."""
    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    strategy_val = _get_strategy(strategy_options)
    return render_template(
        "polymarket_ops.html",
        configured=True,
        active_section="ops",
        polymarket_sections=POLYMARKET_SECTIONS,
        current_strategy=strategy_val,
        strategy_options=strategy_options,
        strategy_options_grouped=strategy_options_grouped,
        data_quality_flags=get_data_quality_flags(data_path),
        **_polymarket_freshness_context(),
    )


# ── Portfolio ─────────────────────────────────────────────────────────────────
@polymarket_bp.route("/portfolio")
@admin_required
@_polymarket_configured_required("portfolio")
def polymarket_portfolio():
    """Display Polymarket Alerts stats from local CSV data."""
    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    strategy_val = _get_strategy(strategy_options)
    filter_val, days_val, days = _parse_filter_days()
    from_date_val = (request.args.get("from_date") or "").strip() or None
    category_val = (request.args.get("category") or "").strip()
    page = max(1, int(request.args.get("page", 1) or 1))
    sort_val = request.args.get("sort", "pnl_asc")
    if sort_val not in SORT_OPTIONS:
        sort_val = "pnl_asc"

    safe_scope = _effective_polymarket_safe_scope()
    stats = get_polymarket_stats(
        data_path,
        filter=filter_val,
        days=days,
        from_date=from_date_val,
        sort=sort_val,
        category=category_val or None,
        strategy=strategy_val,
        safe_scope=safe_scope,
    )
    last_loop = get_last_loop_time(data_path)
    run_stats = get_run_stats_log(data_path)
    status_summary = get_alerts_status_summary(data_path)
    bankroll_status = get_bankroll_status(data_path)
    strategy_overview_groups = get_strategy_summary(data_path)
    # Simulated bets are status='sent' under polymarket-alerts risk guard policy.
    recent_decisions = get_recent_decisions(
        data_path, limit=30, status_filter="sent", strategy=strategy_val, safe_scope=safe_scope
    )
    has_sent_elsewhere = bool(
        status_summary and status_summary.get("sent", 0) > 0 and (stats.get("alerts_total", 0) == 0)
    )

    total_count = len(stats.get("resolved_list", [])) if stats else 0
    pagination = build_pagination(total_count, page, PER_PAGE)
    start = (pagination["page"] - 1) * PER_PAGE
    resolved_page = (stats.get("resolved_list") or [])[start : start + PER_PAGE] if stats else []
    stats_paginated = dict(stats) if stats else {}
    stats_paginated["resolved_list"] = resolved_page

    data_freshness = get_file_age(data_path, "alerts_log.csv")
    return render_template(
        "polymarket.html",
        configured=True,
        stats=stats_paginated,
        total_count=total_count,
        current_filter=filter_val,
        current_days=days_val or "all",
        current_from_date=from_date_val,
        current_category=category_val,
        current_sort=sort_val,
        current_strategy=strategy_val,
        strategy_options=strategy_options,
        sort_options=SORT_OPTIONS,
        last_loop=last_loop,
        run_stats=run_stats,
        status_summary=status_summary,
        bankroll_status=bankroll_status,
        strategy_overview_groups=strategy_overview_groups,
        recent_decisions=recent_decisions,
        has_sent_elsewhere=has_sent_elsewhere,
        data_freshness=data_freshness,
        data_quality_flags=get_data_quality_flags(data_path),
        active_section="portfolio",
        polymarket_sections=POLYMARKET_SECTIONS,
        pagination=pagination,
        strategy_options_grouped=strategy_options_grouped,
        current_safe_scope=safe_scope,
        **_polymarket_freshness_context(),
    )


def _parse_positions_days():
    """Parse days from request for positions time filter."""
    days_val = request.args.get("days", "all")
    days = None
    if days_val != "all":
        try:
            days = int(days_val)
            if days <= 0:
                days = None
        except ValueError:
            days = None
    return days_val or "all", days


# ── Open positions ───────────────────────────────────────────────────────────
@polymarket_bp.route("/positions")
@admin_required
@_polymarket_configured_required("positions")
def polymarket_positions():
    """Open positions from open_positions.csv. Supports marking positions as interesting and filter/sort by them."""
    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    strategy_val = _get_strategy(strategy_options)
    days_val, days = _parse_positions_days()
    from_date_val = (request.args.get("from_date") or "").strip() or None
    category_val = (request.args.get("category") or "").strip() or None
    sort_val = request.args.get("sort", "cost_desc")
    if sort_val not in POSITIONS_SORT_OPTIONS:
        sort_val = "cost_desc"
    interesting_filter = (request.args.get("interesting") or "").strip() == "only"
    expiry_filter_val = (request.args.get("expiry") or "").strip() or None
    if expiry_filter_val not in POSITIONS_EXPIRY_FILTERS:
        expiry_filter_val = None
    hours_max_val = None
    try:
        hm = request.args.get("hours_max", "").strip()
        if hm:
            hours_max_val = float(hm)
    except (ValueError, TypeError):
        pass

    effective_sort = "cost_desc" if sort_val == "interesting_first" else sort_val
    positions = get_open_positions(
        data_path,
        days=days,
        from_date=from_date_val,
        category=category_val,
        sort=effective_sort,
        expiry_filter=expiry_filter_val,
        hours_max=hours_max_val,
        strategy=strategy_val,
    )
    interesting_ids = get_interesting_ids(data_path)
    for p in positions:
        p["is_interesting"] = (p.get("market_id") or "") in interesting_ids
    if interesting_filter:
        positions = [p for p in positions if p.get("is_interesting")]
    if sort_val == "interesting_first":
        positions.sort(key=lambda p: (0 if p.get("is_interesting") else 1, -(p.get("cost_usd") or 0)))

    total_cost = sum(p["cost_usd"] for p in positions)
    total_unrealized = sum(p["unrealized_pnl"] for p in positions)
    exposure = get_exposure_summary(positions)
    data_freshness = get_file_age(data_path, "open_positions.csv")
    bankroll_status = get_bankroll_status(data_path)
    return render_template(
        "polymarket_positions.html",
        configured=True,
        active_section="positions",
        polymarket_sections=POLYMARKET_SECTIONS,
        positions=positions,
        total_cost=total_cost,
        total_cost_display=format_compact_usd(total_cost),
        total_unrealized=total_unrealized,
        total_unrealized_display=format_compact_usd(total_unrealized) if total_unrealized != 0 else None,
        exposure=exposure,
        data_freshness=data_freshness,
        data_quality_flags=get_data_quality_flags(data_path),
        current_days=days_val,
        current_from_date=from_date_val,
        current_category=category_val,
        current_sort=sort_val,
        current_interesting=interesting_filter,
        current_expiry=expiry_filter_val,
        current_hours_max=hours_max_val,
        current_strategy=strategy_val,
        strategy_options=strategy_options,
        strategy_options_grouped=strategy_options_grouped,
        bankroll_status=bankroll_status,
        sort_options=POSITIONS_SORT_OPTIONS,
        expiry_filters=POSITIONS_EXPIRY_FILTERS,
        **_polymarket_freshness_context(),
    )


# Risky threshold presets (edge_min decimal, gamma_max, expiry_hours_max)
RISKY_PRESETS = {
    "conservative": {"edge_min": 0.0125, "gamma_max": 0.90, "expiry_hours_max": 24.0},
    "default": {"edge_min": 0.01, "gamma_max": 0.94, "expiry_hours_max": 48.0},
    "loose": {"edge_min": 0.005, "gamma_max": 0.97, "expiry_hours_max": 72.0},
}


# ── Risky ────────────────────────────────────────────────────────────────────
@polymarket_bp.route("/risky")
@admin_required
@_polymarket_configured_required("risky")
def polymarket_risky():
    """Risky strategy tab: positions matching high edge, low gamma, short expiry."""
    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    strategy_val = _get_strategy(strategy_options)
    days_val, days = _parse_positions_days()
    from_date_val = (request.args.get("from_date") or "").strip() or None
    sort_val = request.args.get("sort", "cost_desc")
    if sort_val not in POSITIONS_SORT_OPTIONS:
        sort_val = "cost_desc"
    preset_val = (request.args.get("preset") or "").strip().lower()
    if preset_val not in RISKY_PRESETS:
        preset_val = None

    criteria = get_risky_criteria()
    if preset_val:
        criteria = {**criteria, **RISKY_PRESETS[preset_val]}

    positions = get_risky_positions(
        data_path,
        days=days,
        from_date=from_date_val,
        sort=sort_val,
        strategy=strategy_val,
        edge_min=criteria["edge_min"],
        gamma_max=criteria["gamma_max"],
        expiry_hours_max=criteria["expiry_hours_max"],
    )
    near_risky_positions = get_near_risky_positions(
        data_path,
        days=days,
        from_date=from_date_val,
        sort=sort_val,
        strategy=strategy_val,
        edge_min=criteria["edge_min"],
        gamma_max=criteria["gamma_max"],
        expiry_hours_max=criteria["expiry_hours_max"],
    )
    total_cost = sum(p.get("cost_usd", 0) for p in positions)
    total_unrealized = sum(p.get("unrealized_pnl", 0) for p in positions)
    exposure = get_exposure_summary(positions)
    risky_historical = get_risky_historical_performance(
        data_path,
        days=days,
        from_date=from_date_val,
        strategy=strategy_val,
        edge_min=criteria["edge_min"],
        gamma_max=criteria["gamma_max"],
        expiry_hours_max=criteria["expiry_hours_max"],
    )
    data_freshness = get_file_age(data_path, "open_positions.csv")

    return render_template(
        "polymarket_risky.html",
        configured=True,
        active_section="risky",
        polymarket_sections=POLYMARKET_SECTIONS,
        positions=positions,
        near_risky_positions=near_risky_positions,
        risky_criteria=criteria,
        risky_historical=risky_historical,
        data_freshness=data_freshness,
        data_quality_flags=get_data_quality_flags(data_path),
        total_cost=total_cost,
        total_cost_display=format_compact_usd(total_cost),
        total_unrealized=total_unrealized,
        total_unrealized_display=format_compact_usd(total_unrealized) if total_unrealized != 0 else None,
        exposure=exposure,
        current_days=days_val,
        current_from_date=from_date_val,
        current_sort=sort_val,
        current_strategy=strategy_val,
        current_preset=preset_val,
        risky_presets=RISKY_PRESETS,
        strategy_options=strategy_options,
        strategy_options_grouped=strategy_options_grouped,
        sort_options=POSITIONS_SORT_OPTIONS,
        **_polymarket_freshness_context(),
    )


@polymarket_bp.route("/positions/refresh", methods=["POST"])
@admin_required
@_polymarket_configured_required("positions")
def polymarket_positions_refresh():
    """Run jobs/update_open_positions.py to refresh open_positions.csv."""
    import subprocess
    data_path = _get_data_path()
    script_path = os.path.join(data_path, "jobs", "update_open_positions.py")
    if not os.path.isfile(script_path):
        flash("jobs/update_open_positions.py not found in polymarket-alerts directory.", "error")
        return redirect(url_for("polymarket.polymarket_positions"))
    # Preserve current filters in redirect (from form hidden fields)
    redirect_kw = {}
    for k in ("days", "category", "sort", "from_date", "expiry", "hours_max", "interesting", "strategy"):
        v = request.form.get(k) or request.args.get(k)
        if v:
            redirect_kw[k] = v
    live_pricing = request.form.get("live_pricing") == "1"
    python_exe = os.path.join(data_path, "venv", "bin", "python") if os.path.isfile(os.path.join(data_path, "venv", "bin", "python")) else "python3"
    cmd = [python_exe, "jobs/update_open_positions.py"]
    if not live_pricing:
        cmd.append("--no-live")
    try:
        result = subprocess.run(
            cmd,
            cwd=data_path,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            out = (result.stdout or "").strip()
            msg = out.split("\n")[-1] if out else "Positions refreshed."
            flash(msg, "success")
        else:
            err = (result.stderr or result.stdout or "").strip()[:300]
            flash(f"Refresh failed: {err or 'Unknown error'}", "error")
    except subprocess.TimeoutExpired:
        flash("Refresh timed out (5 min). Try running manually.", "error")
    except Exception as e:
        flash(f"Refresh failed: {e}", "error")
    return redirect(url_for("polymarket.polymarket_positions", **redirect_kw))


@polymarket_bp.route("/positions/toggle-interesting", methods=["POST"])
@admin_required
@_polymarket_configured_required("positions")
def polymarket_positions_toggle_interesting():
    """Toggle a position's interesting flag by market_id. Returns JSON { ok, is_interesting }."""
    data_path = _get_data_path()
    payload = request.get_json(silent=True) or {}
    market_id = (payload.get("market_id") or request.form.get("market_id") or "").strip()
    if not market_id:
        return jsonify({"ok": False, "error": "market_id required"}), 400
    try:
        is_interesting = toggle_interesting(data_path, market_id)
        return jsonify({"ok": True, "is_interesting": is_interesting})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Loss Lab ──────────────────────────────────────────────────────────────────
@polymarket_bp.route("/loss-lab")
@admin_required
@_polymarket_configured_required("loss-lab")
def polymarket_loss_lab():
    """Loss Lab – breakdown of losses by category."""
    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    strategy_val = _get_strategy(strategy_options)
    _, days_val, days = _parse_filter_days()
    valid, schema_error = validate_alerts_log_schema(data_path)
    loss_breakdown = get_loss_breakdown(data_path, days=days, strategy=strategy_val) if valid else []
    total_losses = sum(item["pnl"] for item in loss_breakdown)
    bucket_breakdowns = get_loss_breakdown_buckets(data_path, days=days, strategy=strategy_val) if valid else {"edge": [], "gamma": [], "hold": [], "time_to_resolution": []}
    trend = get_loss_trend_by_category(data_path, days=days, strategy=strategy_val) if valid else []
    data_freshness = get_file_age(data_path, "alerts_log.csv")
    return render_template(
        "polymarket_loss_lab.html",
        configured=True,
        active_section="loss-lab",
        polymarket_sections=POLYMARKET_SECTIONS,
        loss_breakdown=loss_breakdown,
        total_losses=total_losses,
        total_losses_display=f"${total_losses:.2f}",
        edge_buckets=bucket_breakdowns.get("edge") or [],
        gamma_buckets=bucket_breakdowns.get("gamma") or [],
        hold_buckets=bucket_breakdowns.get("hold") or [],
        ttr_buckets=bucket_breakdowns.get("time_to_resolution") or [],
        loss_trend=trend,
        data_freshness=data_freshness,
        data_quality_flags=get_data_quality_flags(data_path),
        current_days=days_val if days_val else "all",
        current_strategy=strategy_val,
        strategy_options=strategy_options,
        strategy_options_grouped=strategy_options_grouped,
        csv_schema_error=schema_error if not valid else None,
        **_polymarket_freshness_context(),
    )


# ── Analytics ─────────────────────────────────────────────────────────────────
@polymarket_bp.route("/analytics")
@admin_required
@_polymarket_configured_required("analytics")
def polymarket_analytics():
    """Analytics dashboard: Edge Quality, Timing, Strategy Cohort (with drawdown), Exit Study (MTM). Data from analytics.json."""
    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    strategy_val = _get_strategy(strategy_options)
    analytics = get_analytics_json(data_path)
    analytics_age = get_analytics_file_age(data_path)
    # Normalize so template never sees non-dict for strategy_cohort, edge_quality, timing, exit_study, insights
    if analytics is not None and isinstance(analytics, dict):
        analytics = dict(analytics)
        for key in ("strategy_cohort", "edge_quality", "timing", "exit_study", "insights", "ai_policy_pnl_cohort"):
            if analytics.get(key) is not None and not isinstance(analytics.get(key), dict):
                analytics[key] = {}
    return render_template(
        "polymarket_analytics.html",
        configured=True,
        active_section="analytics",
        polymarket_sections=POLYMARKET_SECTIONS,
        analytics=analytics,
        analytics_age=analytics_age,
        data_quality_flags=get_data_quality_flags(data_path),
        current_strategy=strategy_val,
        strategy_options=strategy_options,
        strategy_options_grouped=strategy_options_grouped,
        **_polymarket_freshness_context(),
    )


@polymarket_bp.route("/analytics/refresh", methods=["POST"])
@admin_required
@_polymarket_configured_required("analytics")
def polymarket_analytics_refresh():
    """Run analytics/analytics_export.py to regenerate analytics.json."""
    import subprocess
    data_path = _get_data_path()
    script_path = os.path.join(data_path, "analytics", "analytics_export.py")
    if not os.path.isfile(script_path):
        flash("analytics/analytics_export.py not found in polymarket-alerts directory.", "error")
        return redirect(url_for("polymarket.polymarket_analytics", strategy=request.form.get("strategy") or None))
    python_exe = os.path.join(data_path, "venv", "bin", "python") if os.path.isfile(os.path.join(data_path, "venv", "bin", "python")) else "python3"
    try:
        result = subprocess.run(
            [python_exe, "analytics/analytics_export.py", "--data-dir", data_path, "--out", "analytics.json"],
            cwd=data_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            flash("Analytics refreshed. analytics.json updated.", "success")
        else:
            err = (result.stderr or result.stdout or "").strip()[:300]
            flash(f"Refresh failed: {err or 'Unknown error'}", "error")
    except subprocess.TimeoutExpired:
        flash("Refresh timed out (2 min). Try running manually.", "error")
    except Exception as e:
        flash(f"Refresh failed: {e}", "error")
    return redirect(url_for("polymarket.polymarket_analytics", strategy=request.form.get("strategy") or None))


# ── Lifecycle ─────────────────────────────────────────────────────────────────
@polymarket_bp.route("/lifecycle")
@admin_required
@_polymarket_configured_required("lifecycle")
def polymarket_lifecycle():
    """Strategy lifecycle: promote/kill verdicts from lifecycle.json."""
    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    strategy_val = _get_strategy(strategy_options)
    lifecycle = get_lifecycle_json(data_path)
    lifecycle_age = get_lifecycle_file_age(data_path)
    return render_template(
        "polymarket_lifecycle.html",
        configured=True,
        active_section="lifecycle",
        polymarket_sections=POLYMARKET_SECTIONS,
        lifecycle=lifecycle,
        lifecycle_age=lifecycle_age,
        data_quality_flags=get_data_quality_flags(data_path),
        current_strategy=strategy_val,
        strategy_options=strategy_options,
        strategy_options_grouped=strategy_options_grouped,
        **_polymarket_freshness_context(),
    )


@polymarket_bp.route("/lifecycle/refresh", methods=["POST"])
@admin_required
@_polymarket_configured_required("lifecycle")
def polymarket_lifecycle_refresh():
    """Run analytics/evaluate_strategy_lifecycle.py to regenerate lifecycle.json."""
    import subprocess
    data_path = _get_data_path()
    script_path = os.path.join(data_path, "analytics", "evaluate_strategy_lifecycle.py")
    if not os.path.isfile(script_path):
        flash("analytics/evaluate_strategy_lifecycle.py not found in polymarket-alerts directory.", "error")
        return redirect(url_for("polymarket.polymarket_lifecycle", strategy=request.form.get("strategy") or None))
    python_exe = os.path.join(data_path, "venv", "bin", "python") if os.path.isfile(os.path.join(data_path, "venv", "bin", "python")) else "python3"
    try:
        result = subprocess.run(
            [python_exe, "analytics/evaluate_strategy_lifecycle.py", "--data-dir", data_path, "--out", "lifecycle.json"],
            cwd=data_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            flash("Lifecycle refreshed. lifecycle.json updated.", "success")
        else:
            err = (result.stderr or result.stdout or "").strip()[:300]
            flash(f"Refresh failed: {err or 'Unknown error'}", "error")
    except subprocess.TimeoutExpired:
        flash("Refresh timed out (1 min). Try running manually.", "error")
    except Exception as e:
        flash(f"Refresh failed: {e}", "error")
    return redirect(url_for("polymarket.polymarket_lifecycle", strategy=request.form.get("strategy") or None))


# ── Loop / Dev ───────────────────────────────────────────────────────────────
@polymarket_bp.route("/loop")
@admin_required
@_polymarket_configured_required("loop")
def polymarket_loop():
    """Loop / Dev – debug candidates from debug_candidates.csv."""
    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    strategy_val = _get_strategy(strategy_options)
    last_loop = get_last_loop_time(data_path)
    debug_status = request.args.get("debug_status", "all")
    if debug_status not in ("all", "alert"):
        debug_status = "all"
    debug_sort = request.args.get("debug_sort", "date_desc")
    if debug_sort not in DEBUG_SORT_OPTIONS:
        debug_sort = "date_desc"
    from_date_val = (request.args.get("from_date") or "").strip() or None
    days_val = request.args.get("days", "all")
    days = None
    if days_val != "all":
        try:
            days = int(days_val)
            if days > 0 and not from_date_val:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                from_date_val = cutoff.strftime("%Y-%m-%d")
        except ValueError:
            pass
    hours_max_val = None
    try:
        hm = (request.args.get("hours_max") or "").strip()
        if hm:
            hours_max_val = float(hm)
    except ValueError:
        pass
    debug_result = get_debug_candidates(data_path, status_filter=debug_status, sort=debug_sort, from_date=from_date_val, strategy=strategy_val, hours_max=hours_max_val)
    debug_candidates = []
    debug_total = 0
    debug_page = max(1, int(request.args.get("debug_page", 1) or 1))
    if debug_result:
        debug_all, debug_total = debug_result
        pagination = build_pagination(debug_total, debug_page, DEBUG_PER_PAGE)
        start = (pagination["page"] - 1) * DEBUG_PER_PAGE
        debug_candidates = debug_all[start : start + DEBUG_PER_PAGE]
    else:
        pagination = build_pagination(0, 1, DEBUG_PER_PAGE)
    # Base query params for Loop links (preserve filter when changing sort/page)
    loop_query = {"debug_status": debug_status, "debug_sort": debug_sort, "days": days_val or "all", "from_date": from_date_val or ""}
    if hours_max_val is not None:
        loop_query["hours_max"] = hours_max_val
    data_freshness = get_file_age(data_path, "debug_candidates.csv")
    return render_template(
        "polymarket_loop.html",
        configured=True,
        last_loop=last_loop,
        data_freshness=data_freshness,
        data_quality_flags=get_data_quality_flags(data_path),
        debug_candidates=debug_candidates,
        debug_total=debug_total,
        debug_pagination=pagination,
        debug_status=debug_status,
        debug_sort=debug_sort,
        current_days=days_val or "all",
        current_from_date=from_date_val,
        current_hours_max=hours_max_val,
        loop_hours_presets=LOOP_HOURS_MAX_PRESETS,
        loop_query=loop_query,
        current_strategy=strategy_val,
        strategy_options=strategy_options,
        strategy_options_grouped=strategy_options_grouped,
        active_section="loop",
        polymarket_sections=POLYMARKET_SECTIONS,
        **_polymarket_freshness_context(),
    )


# ── Scorecard (Phase 1) ───────────────────────────────────────────────────────
@polymarket_bp.route("/scorecard")
@admin_required
@_polymarket_configured_required("scorecard")
def polymarket_scorecard():
    """
    Per-strategy scorecard. Default response is HTML (Chunk 1c). Use ``format=json`` for JSON.
    Query: ``safe_scope``, ``days`` (all | 7 | 30), ``sort``, ``order``.
    """
    fmt = (request.args.get("format") or "html").strip().lower()
    if fmt not in ("json", "html"):
        fmt = "html"

    safe_scope = _effective_polymarket_safe_scope()
    days = _parse_scorecard_days()
    days_disp = _parse_scorecard_days_display()

    sort_col = (request.args.get("sort") or "pnl").strip().lower()
    if sort_col not in _SCORECARD_SORT_KEYS:
        sort_col = "pnl"
    order = (request.args.get("order") or "desc").strip().lower()
    if order not in ("asc", "desc"):
        order = "desc"

    data_path = _get_data_path()
    rows = get_strategy_scorecard(data_path, safe_scope=safe_scope, days=days)
    rows = _sort_scorecard_rows(rows, sort_col, order)

    if fmt == "json":
        return jsonify(rows)

    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    current_strategy = _get_strategy(strategy_options)

    sort_href = {
        col: _scorecard_sort_href(
            col,
            safe_scope=safe_scope,
            days_disp=days_disp,
            sort_col=sort_col,
            order=order,
        )
        for col in _SCORECARD_SORT_KEYS
    }

    return render_template(
        "polymarket_scorecard.html",
        polymarket_sections=POLYMARKET_SECTIONS,
        active_section="scorecard",
        strategy_options=strategy_options,
        strategy_options_grouped=strategy_options_grouped,
        current_strategy=current_strategy,
        STRATEGY_LABELS=STRATEGY_LABELS,
        scorecard_rows=rows,
        current_safe_scope=safe_scope,
        current_days_scorecard=days_disp,
        current_scorecard_sort=sort_col,
        current_scorecard_order=order,
        scorecard_sort_href=sort_href,
        data_quality_flags=get_data_quality_flags(data_path),
        **_polymarket_freshness_context(),
    )


# ── AI Simulation ─────────────────────────────────────────────────────────────
@polymarket_bp.route("/ai-simulation")
@admin_required
@_polymarket_configured_required("ai-simulation")
def polymarket_ai_simulation():
    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    current_strategy = _get_strategy(strategy_options)
    data_quality_flags = get_data_quality_flags(data_path)

    filter_val, days_val, days = _parse_filter_days()
    sort_val = request.args.get("sort", "date_desc")
    if sort_val not in ("pnl_asc", "pnl_desc", "date_desc", "date_asc"):
        sort_val = "date_desc"
    safe_scope = _effective_polymarket_safe_scope()
    page = max(1, int(request.args.get("page", 1) or 1))

    sim = get_ai_sim_stats(
        data_path,
        filter=filter_val,
        days=days,
        sort=sort_val,
        strategy=current_strategy,
        safe_scope=safe_scope,
    )

    total_count = len(sim.get("resolved_list", [])) if sim else 0
    pagination = build_pagination(total_count, page, PER_PAGE)
    start = (pagination["page"] - 1) * PER_PAGE
    resolved_page = (sim.get("resolved_list") or [])[start: start + PER_PAGE] if sim else []
    sim_paginated = dict(sim) if sim else {}
    sim_paginated["resolved_list"] = resolved_page

    return render_template(
        "polymarket_ai_simulation.html",
        polymarket_sections=POLYMARKET_SECTIONS,
        active_section="ai-simulation",
        strategy_options=strategy_options,
        strategy_options_grouped=strategy_options_grouped,
        current_strategy=current_strategy,
        STRATEGY_LABELS=STRATEGY_LABELS,
        data_quality_flags=data_quality_flags,
        sim=sim_paginated,
        total_count=total_count,
        pagination=pagination,
        current_filter=filter_val,
        current_days=days_val,
        current_sort=sort_val,
        current_safe_scope=safe_scope,
        **_polymarket_freshness_context(),
    )


# ── Mirror Portfolio (read-only trade mirror export) ─────────────────────────
@polymarket_bp.route("/mirror-portfolio")
@admin_required
@_polymarket_configured_required("mirror-portfolio")
def polymarket_mirror_portfolio():
    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    current_strategy = _get_strategy(strategy_options)
    data_quality_flags = get_data_quality_flags(data_path)
    mirror = get_mirror_portfolio_json(data_path)
    mirror_age = get_mirror_portfolio_file_age(data_path)
    mirror_wallet_prefill = (request.args.get("mirror_wallet") or "").strip()
    mirror_days_prefill = (request.args.get("mirror_days") or "").strip()
    if not mirror_wallet_prefill and mirror and isinstance(mirror.get("meta"), dict):
        mirror_wallet_prefill = (mirror["meta"].get("wallet") or "").strip()
    if not mirror_days_prefill:
        mirror_days_prefill = (os.getenv("MIRROR_DAYS") or "365").strip() or "365"
    return render_template(
        "polymarket_mirror_portfolio.html",
        polymarket_sections=POLYMARKET_SECTIONS,
        active_section="mirror-portfolio",
        strategy_options=strategy_options,
        strategy_options_grouped=strategy_options_grouped,
        current_strategy=current_strategy,
        STRATEGY_LABELS=STRATEGY_LABELS,
        data_quality_flags=data_quality_flags,
        mirror=mirror,
        mirror_age=mirror_age,
        mirror_wallet_prefill=mirror_wallet_prefill,
        mirror_days_prefill=mirror_days_prefill,
        **_polymarket_freshness_context(),
    )


@polymarket_bp.route("/mirror-portfolio/refresh", methods=["POST"])
@admin_required
@_polymarket_configured_required("mirror-portfolio")
def polymarket_mirror_portfolio_refresh():
    """Regenerate mirror_portfolio.json via analytics/mirror_portfolio_export.py."""
    import subprocess

    data_path = _get_data_path()
    script_path = os.path.join(data_path, "analytics", "mirror_portfolio_export.py")
    strategy_q = request.form.get("strategy") or None
    form_wallet = (request.form.get("wallet") or "").strip()
    form_days = (request.form.get("days") or "").strip()
    wallet = _normalize_mirror_wallet(form_wallet) or _normalize_mirror_wallet(os.getenv("MIRROR_WALLET") or "")
    days = _parse_mirror_days(form_days or os.getenv("MIRROR_DAYS") or "365")

    def _redirect_with_form(**extra):
        kw = {"strategy": strategy_q, "mirror_wallet": form_wallet or "", "mirror_days": form_days or days}
        kw.update(extra)
        return redirect(url_for("polymarket.polymarket_mirror_portfolio", **kw))

    if not os.path.isfile(script_path):
        flash("analytics/mirror_portfolio_export.py not found in polymarket-alerts directory.", "error")
        return _redirect_with_form()
    if not wallet:
        flash("Enter a valid wallet address (0x + 40 hex characters), or set MIRROR_WALLET in .env.", "error")
        return _redirect_with_form()
    python_exe = os.path.join(data_path, "venv", "bin", "python") if os.path.isfile(os.path.join(data_path, "venv", "bin", "python")) else "python3"
    try:
        result = subprocess.run(
            [
                python_exe,
                "analytics/mirror_portfolio_export.py",
                "--data-dir",
                data_path,
                "--wallet",
                wallet,
                "--days",
                days,
            ],
            cwd=data_path,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            flash("mirror_portfolio.json updated.", "success")
        else:
            err = (result.stderr or result.stdout or "").strip()[:400]
            flash(f"Refresh failed: {err or 'Unknown error'}", "error")
    except subprocess.TimeoutExpired:
        flash("Refresh timed out (5 min). Try running manually on the server.", "error")
    except Exception as e:
        flash(f"Refresh failed: {e}", "error")
    return redirect(
        url_for(
            "polymarket.polymarket_mirror_portfolio",
            strategy=strategy_q,
            mirror_wallet=wallet,
            mirror_days=days,
        )
    )


# ── Mirror alerts (multi-wallet Telegram watch list) ──────────────────────────
@polymarket_bp.route("/mirror-alerts")
@admin_required
@_polymarket_configured_required("mirror-alerts")
def polymarket_mirror_alerts():
    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    current_strategy = _get_strategy(strategy_options)
    data_quality_flags = get_data_quality_flags(data_path)
    cfg = get_mirror_watch_config(data_path) or {"version": 1, "wallets": []}
    wallets = cfg.get("wallets") if isinstance(cfg.get("wallets"), list) else []
    cfg_age = get_file_age(data_path, "mirror_watch_config.json")
    mirror_min_notional_usd = None
    if isinstance(cfg, dict) and "min_notional_usd" in cfg:
        try:
            mirror_min_notional_usd = max(0.0, float(cfg["min_notional_usd"]))
        except (TypeError, ValueError):
            mirror_min_notional_usd = None
    return render_template(
        "polymarket_mirror_alerts.html",
        polymarket_sections=POLYMARKET_SECTIONS,
        active_section="mirror-alerts",
        strategy_options=strategy_options,
        strategy_options_grouped=strategy_options_grouped,
        current_strategy=current_strategy,
        STRATEGY_LABELS=STRATEGY_LABELS,
        data_quality_flags=data_quality_flags,
        wallets=wallets,
        mirror_watch_max=MIRROR_WATCH_MAX_WALLETS,
        mirror_poll_groups=MIRROR_POLL_GROUPS,
        cfg_age=cfg_age,
        mirror_min_notional_usd=mirror_min_notional_usd,
        **_polymarket_freshness_context(),
    )


@polymarket_bp.route("/mirror-alerts/add", methods=["POST"])
@admin_required
@_polymarket_configured_required("mirror-alerts")
def polymarket_mirror_alerts_add():
    data_path = _get_data_path()
    addr = _normalize_mirror_wallet((request.form.get("address") or "").strip())
    label = (request.form.get("label") or "").strip()[:80] or None
    telegram_on = request.form.get("telegram_enabled") == "on"
    poll_group = normalize_mirror_poll_group(request.form.get("poll_group"))
    if not addr:
        flash("Enter a valid wallet address (0x + 40 hex characters).", "error")
        return redirect(url_for("polymarket.polymarket_mirror_alerts", strategy=request.form.get("strategy") or None))
    cfg = get_mirror_watch_config(data_path) or {"wallets": []}
    wallets = list(cfg.get("wallets") or [])
    if len(wallets) >= MIRROR_WATCH_MAX_WALLETS:
        flash(f"Maximum {MIRROR_WATCH_MAX_WALLETS} wallets.", "error")
        return redirect(url_for("polymarket.polymarket_mirror_alerts", strategy=request.form.get("strategy") or None))
    if any((w.get("address") or "").lower() == addr for w in wallets if isinstance(w, dict)):
        flash("That address is already in the list.", "error")
        return redirect(url_for("polymarket.polymarket_mirror_alerts", strategy=request.form.get("strategy") or None))
    wallets.append(
        {
            "id": uuid.uuid4().hex[:12],
            "address": addr,
            "label": label or (addr[:10] + "…"),
            "telegram_enabled": telegram_on,
            "poll_group": poll_group,
        }
    )
    ok, err = save_mirror_watch_config(data_path, {"wallets": wallets})
    if ok:
        flash("Wallet added. First timer run will seed trades (no Telegram spam).", "success")
    else:
        flash(f"Could not save config: {err}", "error")
    return redirect(url_for("polymarket.polymarket_mirror_alerts", strategy=request.form.get("strategy") or None))


@polymarket_bp.route("/mirror-alerts/toggle-telegram", methods=["POST"])
@admin_required
@_polymarket_configured_required("mirror-alerts")
def polymarket_mirror_alerts_toggle_telegram():
    data_path = _get_data_path()
    addr = _normalize_mirror_wallet((request.form.get("address") or "").strip())
    if not addr:
        flash("Invalid address.", "error")
        return redirect(url_for("polymarket.polymarket_mirror_alerts", strategy=request.form.get("strategy") or None))
    cfg = get_mirror_watch_config(data_path) or {"wallets": []}
    wallets = []
    for w in cfg.get("wallets") or []:
        if not isinstance(w, dict):
            continue
        w = dict(w)
        if (w.get("address") or "").lower() == addr:
            w["telegram_enabled"] = not bool(w.get("telegram_enabled", True))
        wallets.append(w)
    ok, err = save_mirror_watch_config(data_path, {"wallets": wallets})
    if ok:
        flash("Telegram setting updated.", "success")
    else:
        flash(f"Could not save: {err}", "error")
    return redirect(url_for("polymarket.polymarket_mirror_alerts", strategy=request.form.get("strategy") or None))


@polymarket_bp.route("/mirror-alerts/set-poll-group", methods=["POST"])
@admin_required
@_polymarket_configured_required("mirror-alerts")
def polymarket_mirror_alerts_set_poll_group():
    data_path = _get_data_path()
    addr = _normalize_mirror_wallet((request.form.get("address") or "").strip())
    poll_group = normalize_mirror_poll_group(request.form.get("poll_group"))
    if not addr:
        flash("Invalid address.", "error")
        return redirect(url_for("polymarket.polymarket_mirror_alerts", strategy=request.form.get("strategy") or None))
    cfg = get_mirror_watch_config(data_path) or {"wallets": []}
    wallets = []
    for w in cfg.get("wallets") or []:
        if not isinstance(w, dict):
            continue
        w = dict(w)
        if (w.get("address") or "").lower() == addr:
            w["poll_group"] = poll_group
        wallets.append(w)
    ok, err = save_mirror_watch_config(data_path, {"wallets": wallets})
    if ok:
        flash("Poll group updated.", "success")
    else:
        flash(f"Could not save: {err}", "error")
    return redirect(url_for("polymarket.polymarket_mirror_alerts", strategy=request.form.get("strategy") or None))


@polymarket_bp.route("/mirror-alerts/remove", methods=["POST"])
@admin_required
@_polymarket_configured_required("mirror-alerts")
def polymarket_mirror_alerts_remove():
    data_path = _get_data_path()
    addr = _normalize_mirror_wallet((request.form.get("address") or "").strip())
    if not addr:
        flash("Invalid address.", "error")
        return redirect(url_for("polymarket.polymarket_mirror_alerts", strategy=request.form.get("strategy") or None))
    cfg = get_mirror_watch_config(data_path) or {"wallets": []}
    wallets = [w for w in (cfg.get("wallets") or []) if isinstance(w, dict) and (w.get("address") or "").lower() != addr]
    ok, err = save_mirror_watch_config(data_path, {"wallets": wallets})
    if ok:
        flash("Wallet removed from watch list.", "success")
    else:
        flash(f"Could not save: {err}", "error")
    return redirect(url_for("polymarket.polymarket_mirror_alerts", strategy=request.form.get("strategy") or None))


# ── AI Performance ────────────────────────────────────────────────────────────
@polymarket_bp.route("/ai-performance")
@admin_required
@_polymarket_configured_required("ai-performance")
def polymarket_ai_performance():
    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_options_grouped = get_strategy_options_grouped(strategy_options)
    current_strategy = _get_strategy(strategy_options)
    data_quality_flags = get_data_quality_flags(data_path)
    ai_perf = get_ai_performance(data_path, strategy=current_strategy)
    return render_template(
        "polymarket_ai_performance.html",
        polymarket_sections=POLYMARKET_SECTIONS,
        active_section="ai-performance",
        strategy_options=strategy_options,
        strategy_options_grouped=strategy_options_grouped,
        current_strategy=current_strategy,
        STRATEGY_LABELS=STRATEGY_LABELS,
        data_quality_flags=data_quality_flags,
        ai_perf=ai_perf,
        **_polymarket_freshness_context(),
    )


# ── Export ───────────────────────────────────────────────────────────────────
@polymarket_bp.route("/export")
@admin_required
def polymarket_export():
    """Export filtered resolved list as CSV download."""
    if not is_polymarket_configured():
        return "Polymarket not configured", 404

    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_val = _get_strategy(strategy_options)
    filter_val, _, days = _parse_filter_days()
    from_date_val = (request.args.get("from_date") or "").strip() or None
    category_val = (request.args.get("category") or "").strip() or None
    sort_val = request.args.get("sort", "pnl_asc")
    if sort_val not in SORT_OPTIONS:
        sort_val = "pnl_asc"

    safe_scope = _effective_polymarket_safe_scope()
    stats = get_polymarket_stats(
        data_path,
        filter=filter_val,
        days=days,
        from_date=from_date_val,
        sort=sort_val,
        category=category_val,
        strategy=strategy_val,
        safe_scope=safe_scope,
    )
    if not stats or "resolved_list" not in stats:
        return "No data to export", 404

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["question", "pick", "result", "result_detail", "pnl_usd", "link"])
    for r in stats["resolved_list"]:
        writer.writerow([
            r.get("question", ""),
            r.get("outcome_label", "") or r.get("pick_display", ""),
            r.get("actual_result", ""),
            r.get("result_detail_display", r.get("actual_result", "")),
            r.get("pnl_usd", 0),
            r.get("link", ""),
        ])

    output.seek(0)
    filename = f"polymarket_resolved_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


@polymarket_bp.route("/export-debug")
@admin_required
def polymarket_export_debug():
    """Export debug_candidates_v60.csv (Loop Summary full data) as CSV download."""
    if not is_polymarket_configured():
        return "Polymarket not configured", 404

    data_path = _get_data_path()
    strategy_options = get_strategy_options_for_nav(data_path)
    strategy_val = _get_strategy(strategy_options)
    result = get_debug_candidates(data_path, strategy=strategy_val)
    if not result:
        return "Debug candidates file not found", 404

    debug_all, _ = result
    if not debug_all:
        return "No debug candidates data", 404

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ts", "question", "gamma", "best_ask", "spread", "effective", "fill_pct", "edge", "days", "status"])
    for r in debug_all:
        writer.writerow([
            r.get("ts", ""),
            r.get("question", ""),
            r.get("gamma", ""),
            r.get("best_ask", ""),
            r.get("spread", ""),
            r.get("effective", ""),
            r.get("fill_pct", ""),
            r.get("edge", ""),
            r.get("days", ""),
            r.get("status", ""),
        ])

    output.seek(0)
    filename = f"debug_candidates_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )
