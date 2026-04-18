"""Site root and legacy URL stubs (Phase 5c — replaces ``public`` blueprint)."""

from flask import Blueprint, abort, redirect, url_for

root_bp = Blueprint("root", __name__)


@root_bp.route("/")
def index():
    return redirect(url_for("polymarket.polymarket_scorecard"), code=302)


@root_bp.route("/feed.xml")
def rss_feed_gone():
    abort(404)


@root_bp.route("/rss")
def rss_alias_gone():
    abort(404)
