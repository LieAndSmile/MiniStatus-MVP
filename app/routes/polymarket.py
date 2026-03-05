from flask import Blueprint, render_template, request, send_file, redirect, url_for, flash, jsonify
from functools import wraps
import os
import csv
import io
from datetime import datetime, timedelta, timezone

from app.utils.polymarket import (
    get_polymarket_stats,
    is_polymarket_configured,
    get_last_loop_time,
    get_run_stats_log,
    get_loss_breakdown,
    get_debug_candidates,
    get_open_positions,
    get_risky_positions,
    get_risky_criteria,
    get_interesting_ids,
    toggle_interesting,
    get_expectancy_by_bands,
    get_exposure_summary,
    validate_alerts_log_schema,
    format_compact_usd,
    build_pagination,
    SORT_OPTIONS,
    DEBUG_SORT_OPTIONS,
    POSITIONS_SORT_OPTIONS,
    POSITIONS_EXPIRY_FILTERS,
)
from app.utils.decorators import admin_required

polymarket_bp = Blueprint("polymarket", __name__, url_prefix="/polymarket")


PER_PAGE = 50
DEBUG_PER_PAGE = 100

POLYMARKET_SECTIONS = [
    ("portfolio", "Portfolio", "polymarket.polymarket_portfolio"),
    ("positions", "Open Positions", "polymarket.polymarket_positions"),
    ("risky", "Risky", "polymarket.polymarket_risky"),
    ("performance", "Performance", "polymarket.polymarket_performance"),
    ("loss-lab", "Loss Lab", "polymarket.polymarket_loss_lab"),
    ("loop", "Loop / Dev", "polymarket.polymarket_loop"),
]


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


@polymarket_bp.route("")
@polymarket_bp.route("/")
@admin_required
def polymarket_index():
    """Redirect /polymarket to /polymarket/portfolio (default landing)."""
    return redirect(url_for("polymarket.polymarket_portfolio"))


@polymarket_bp.route("/portfolio")
@admin_required
@_polymarket_configured_required("portfolio")
def polymarket_portfolio():
    """Display Polymarket Alerts stats from local CSV data."""
    data_path = _get_data_path()
    filter_val, days_val, days = _parse_filter_days()
    from_date_val = (request.args.get("from_date") or "").strip() or None
    category_val = (request.args.get("category") or "").strip()
    page = max(1, int(request.args.get("page", 1) or 1))
    sort_val = request.args.get("sort", "pnl_asc")
    if sort_val not in SORT_OPTIONS:
        sort_val = "pnl_asc"

    stats = get_polymarket_stats(data_path, filter=filter_val, days=days, from_date=from_date_val, sort=sort_val, category=category_val or None)
    last_loop = get_last_loop_time(data_path)
    run_stats = get_run_stats_log(data_path)

    total_count = len(stats.get("resolved_list", [])) if stats else 0
    pagination = build_pagination(total_count, page, PER_PAGE)
    start = (pagination["page"] - 1) * PER_PAGE
    resolved_page = (stats.get("resolved_list") or [])[start : start + PER_PAGE] if stats else []
    stats_paginated = dict(stats) if stats else {}
    stats_paginated["resolved_list"] = resolved_page

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
        sort_options=SORT_OPTIONS,
        last_loop=last_loop,
        run_stats=run_stats,
        active_section="portfolio",
        polymarket_sections=POLYMARKET_SECTIONS,
        pagination=pagination,
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


@polymarket_bp.route("/positions")
@admin_required
@_polymarket_configured_required("positions")
def polymarket_positions():
    """Open positions from open_positions.csv. Supports marking positions as interesting and filter/sort by them."""
    data_path = _get_data_path()
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
        current_days=days_val,
        current_from_date=from_date_val,
        current_category=category_val,
        current_sort=sort_val,
        current_interesting=interesting_filter,
        current_expiry=expiry_filter_val,
        current_hours_max=hours_max_val,
        sort_options=POSITIONS_SORT_OPTIONS,
        expiry_filters=POSITIONS_EXPIRY_FILTERS,
    )


@polymarket_bp.route("/risky")
@admin_required
@_polymarket_configured_required("risky")
def polymarket_risky():
    """Risky strategy tab: positions matching high edge, low gamma, short expiry."""
    data_path = _get_data_path()
    days_val, days = _parse_positions_days()
    from_date_val = (request.args.get("from_date") or "").strip() or None
    sort_val = request.args.get("sort", "cost_desc")
    if sort_val not in POSITIONS_SORT_OPTIONS:
        sort_val = "cost_desc"

    criteria = get_risky_criteria()
    positions = get_risky_positions(
        data_path,
        days=days,
        from_date=from_date_val,
        sort=sort_val,
    )
    total_cost = sum(p["cost_usd"] for p in positions)
    total_unrealized = sum(p["unrealized_pnl"] for p in positions)
    exposure = get_exposure_summary(positions)

    return render_template(
        "polymarket_risky.html",
        configured=True,
        active_section="risky",
        polymarket_sections=POLYMARKET_SECTIONS,
        positions=positions,
        risky_criteria=criteria,
        total_cost=total_cost,
        total_cost_display=format_compact_usd(total_cost),
        total_unrealized=total_unrealized,
        total_unrealized_display=format_compact_usd(total_unrealized) if total_unrealized != 0 else None,
        exposure=exposure,
        current_days=days_val,
        current_from_date=from_date_val,
        current_sort=sort_val,
        sort_options=POSITIONS_SORT_OPTIONS,
    )


@polymarket_bp.route("/positions/refresh", methods=["POST"])
@admin_required
@_polymarket_configured_required("positions")
def polymarket_positions_refresh():
    """Run update_open_positions.py to refresh open_positions.csv."""
    import subprocess
    data_path = _get_data_path()
    script_path = os.path.join(data_path, "update_open_positions.py")
    if not os.path.isfile(script_path):
        flash("update_open_positions.py not found in polymarket-alerts directory.", "error")
        return redirect(url_for("polymarket.polymarket_positions"))
    # Preserve current filters in redirect (from form hidden fields)
    redirect_kw = {}
    for k in ("days", "category", "sort", "from_date", "expiry", "hours_max", "interesting"):
        v = request.form.get(k) or request.args.get(k)
        if v:
            redirect_kw[k] = v
    try:
        result = subprocess.run(
            ["python3", "update_open_positions.py", "--no-live"],
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


@polymarket_bp.route("/performance")
@admin_required
@_polymarket_configured_required("performance")
def polymarket_performance():
    """Performance analytics – expectancy by edge/gamma bands."""
    data_path = _get_data_path()
    _, days_val, days = _parse_filter_days()
    expectancy = get_expectancy_by_bands(data_path, days=days)
    return render_template(
        "polymarket_performance.html",
        configured=True,
        active_section="performance",
        polymarket_sections=POLYMARKET_SECTIONS,
        edge_bands=expectancy.get("edge_bands", []),
        gamma_bands=expectancy.get("gamma_bands", []),
        insight_edge=expectancy.get("insight_edge"),
        insight_gamma=expectancy.get("insight_gamma"),
        current_days=days_val if days_val else "all",
    )


@polymarket_bp.route("/loss-lab")
@admin_required
@_polymarket_configured_required("loss-lab")
def polymarket_loss_lab():
    """Loss Lab – breakdown of losses by category."""
    data_path = _get_data_path()
    _, days_val, days = _parse_filter_days()
    valid, schema_error = validate_alerts_log_schema(data_path)
    loss_breakdown = get_loss_breakdown(data_path, days=days) if valid else []
    total_losses = sum(item["pnl"] for item in loss_breakdown)
    return render_template(
        "polymarket_loss_lab.html",
        configured=True,
        active_section="loss-lab",
        polymarket_sections=POLYMARKET_SECTIONS,
        loss_breakdown=loss_breakdown,
        total_losses=total_losses,
        total_losses_display=f"${total_losses:.2f}",
        current_days=days_val if days_val else "all",
        csv_schema_error=schema_error if not valid else None,
    )


@polymarket_bp.route("/loop")
@admin_required
@_polymarket_configured_required("loop")
def polymarket_loop():
    """Loop / Dev – debug candidates from debug_candidates_v60.csv."""
    data_path = _get_data_path()
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
    debug_result = get_debug_candidates(data_path, status_filter=debug_status, sort=debug_sort, from_date=from_date_val)
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
    return render_template(
        "polymarket_loop.html",
        configured=True,
        last_loop=last_loop,
        debug_candidates=debug_candidates,
        debug_total=debug_total,
        debug_pagination=pagination,
        debug_status=debug_status,
        debug_sort=debug_sort,
        current_days=days_val or "all",
        current_from_date=from_date_val,
        active_section="loop",
        polymarket_sections=POLYMARKET_SECTIONS,
    )


@polymarket_bp.route("/export")
@admin_required
def polymarket_export():
    """Export filtered resolved list as CSV download."""
    if not is_polymarket_configured():
        return "Polymarket not configured", 404

    data_path = _get_data_path()
    filter_val, _, days = _parse_filter_days()
    from_date_val = (request.args.get("from_date") or "").strip() or None
    category_val = (request.args.get("category") or "").strip() or None
    sort_val = request.args.get("sort", "pnl_asc")
    if sort_val not in SORT_OPTIONS:
        sort_val = "pnl_asc"

    stats = get_polymarket_stats(data_path, filter=filter_val, days=days, from_date=from_date_val, sort=sort_val, category=category_val)
    if not stats or "resolved_list" not in stats:
        return "No data to export", 404

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["question", "result", "pnl_usd", "link"])
    for r in stats["resolved_list"]:
        writer.writerow([
            r.get("question", ""),
            r.get("actual_result", ""),
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
    result = get_debug_candidates(data_path)
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
