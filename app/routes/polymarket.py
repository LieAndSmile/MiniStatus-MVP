from flask import Blueprint, render_template, request, send_file
import os
import csv
import io
from datetime import datetime

from app.utils.polymarket import get_polymarket_stats, is_polymarket_configured, get_last_loop_time, get_run_stats_log, get_loss_breakdown, get_debug_candidates, SORT_OPTIONS, DEBUG_SORT_OPTIONS
from app.utils.decorators import admin_required

polymarket_bp = Blueprint("polymarket", __name__)


PER_PAGE = 50
DEBUG_PER_PAGE = 100


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
    return filter_val, days


def _pagination_params():
    """Build dict of filter/days/page for URL query strings."""
    filter_val, days = _parse_filter_days()
    days_val = request.args.get("days", "all")
    page = max(1, int(request.args.get("page", 1) or 1))
    return {"filter": filter_val, "days": days_val or "all", "page": page}


@polymarket_bp.route("/polymarket")
@admin_required
def polymarket_page():
    """Display Polymarket Alerts stats from local CSV data."""
    if not is_polymarket_configured():
        return render_template(
            "polymarket.html",
            configured=False,
            stats=None,
        )

    data_path = os.getenv("POLYMARKET_DATA_PATH", "").strip()
    filter_val, days = _parse_filter_days()
    days_val = request.args.get("days", "all")
    page = max(1, int(request.args.get("page", 1) or 1))
    sort_val = request.args.get("sort", "pnl_asc")
    if sort_val not in SORT_OPTIONS:
        sort_val = "pnl_asc"

    stats = get_polymarket_stats(data_path, filter=filter_val, days=days, sort=sort_val)
    last_loop = get_last_loop_time(data_path)
    run_stats = get_run_stats_log(data_path)
    loss_breakdown = get_loss_breakdown(data_path, days=days)

    # Loop Summary / debug candidates (Full data → debug_candidates_v60.csv)
    debug_status = request.args.get("debug_status", "all")
    if debug_status not in ("all", "alert"):
        debug_status = "all"
    debug_sort = request.args.get("debug_sort", "date_desc")
    if debug_sort not in DEBUG_SORT_OPTIONS:
        debug_sort = "date_desc"
    debug_result = get_debug_candidates(data_path, status_filter=debug_status, sort=debug_sort)
    debug_candidates = []
    debug_total = 0
    debug_total_pages = 1
    debug_page = max(1, int(request.args.get("debug_page", 1) or 1))
    if debug_result:
        debug_all, debug_total = debug_result
        debug_total_pages = max(1, (debug_total + DEBUG_PER_PAGE - 1) // DEBUG_PER_PAGE)
        debug_page = min(debug_page, debug_total_pages)
        start = (debug_page - 1) * DEBUG_PER_PAGE
        debug_candidates = debug_all[start : start + DEBUG_PER_PAGE]

    total_count = len(stats.get("resolved_list", [])) if stats else 0
    total_pages = max(1, (total_count + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    resolved_page = (stats.get("resolved_list") or [])[start:end] if stats else []
    stats_paginated = dict(stats) if stats else {}
    stats_paginated["resolved_list"] = resolved_page

    return render_template(
        "polymarket.html",
        configured=True,
        stats=stats_paginated,
        total_count=total_count,
        current_filter=filter_val,
        current_days=days_val if days_val else "all",
        current_sort=sort_val,
        sort_options=SORT_OPTIONS,
        last_loop=last_loop,
        run_stats=run_stats,
        loss_breakdown=loss_breakdown,
        debug_candidates=debug_candidates,
        debug_total=debug_total,
        debug_pagination={
            "page": debug_page,
            "per_page": DEBUG_PER_PAGE,
            "total_pages": debug_total_pages,
            "total_count": debug_total,
            "has_prev": debug_page > 1,
            "has_next": debug_page < debug_total_pages,
            "start": (debug_page - 1) * DEBUG_PER_PAGE + 1 if debug_total else 0,
            "end": min(debug_page * DEBUG_PER_PAGE, debug_total),
        },
        debug_status=debug_status,
        debug_sort=debug_sort,
        active_tab=request.args.get("tab", "resolved"),
        pagination={
            "page": page,
            "per_page": PER_PAGE,
            "total_pages": total_pages,
            "total_count": total_count,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "start": start + 1 if total_count else 0,
            "end": min(end, total_count),
        },
    )


@polymarket_bp.route("/polymarket/export")
@admin_required
def polymarket_export():
    """Export filtered resolved list as CSV download."""
    if not is_polymarket_configured():
        return "Polymarket not configured", 404

    data_path = os.getenv("POLYMARKET_DATA_PATH", "").strip()
    filter_val, days = _parse_filter_days()
    sort_val = request.args.get("sort", "pnl_asc")
    if sort_val not in SORT_OPTIONS:
        sort_val = "pnl_asc"

    stats = get_polymarket_stats(data_path, filter=filter_val, days=days, sort=sort_val)
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


@polymarket_bp.route("/polymarket/export-debug")
@admin_required
def polymarket_export_debug():
    """Export debug_candidates_v60.csv (Loop Summary full data) as CSV download."""
    if not is_polymarket_configured():
        return "Polymarket not configured", 404

    data_path = os.getenv("POLYMARKET_DATA_PATH", "").strip()
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
