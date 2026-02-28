from flask import Blueprint, render_template, request, send_file
import os
import csv
import io
from datetime import datetime

from app.utils.polymarket import get_polymarket_stats, is_polymarket_configured, get_last_loop_time
from app.utils.decorators import admin_required

polymarket_bp = Blueprint("polymarket", __name__)


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

    stats = get_polymarket_stats(data_path, filter=filter_val, days=days)
    last_loop = get_last_loop_time(data_path)

    return render_template(
        "polymarket.html",
        configured=True,
        stats=stats,
        current_filter=filter_val,
        current_days=days_val if days_val else "all",
        last_loop=last_loop,
    )


@polymarket_bp.route("/polymarket/export")
@admin_required
def polymarket_export():
    """Export filtered resolved list as CSV download."""
    if not is_polymarket_configured():
        return "Polymarket not configured", 404

    data_path = os.getenv("POLYMARKET_DATA_PATH", "").strip()
    filter_val, days = _parse_filter_days()

    stats = get_polymarket_stats(data_path, filter=filter_val, days=days)
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
