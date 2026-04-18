# app/routes/public.py — Phase 1.5: site root redirects to Polymarket scorecard; legacy public dashboard removed.

from flask import Blueprint, abort, redirect, url_for

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    """Redirect home to the Polymarket operator console (requires login for scorecard)."""
    return redirect(url_for("polymarket.polymarket_scorecard"), code=302)


@public_bp.route("/feed.xml")
def rss_feed():
    """Legacy RSS feed (service monitor); removed in Tier 2."""
    abort(404)


@public_bp.route("/rss")
def rss_redirect():
    """Legacy RSS alias; removed in Tier 2."""
    abort(404)
