"""Tier 3 smoke: app boots without legacy service-monitor stack."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_create_app():
    from app import create_app

    app = create_app()
    assert app is not None


def test_polymarket_routes_exist():
    from app import create_app

    app = create_app()
    paths = {str(r.rule) for r in app.url_map.iter_rules()}
    assert "/polymarket/portfolio" in paths
    assert "/" in paths


def test_no_sqlalchemy_in_extensions():
    from app import extensions

    assert not hasattr(extensions, "db")


def test_change_password_page_renders():
    """Cancel link must use a live route (admin.dashboard was removed in Tier 3)."""
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["authenticated"] = True
        r = c.get("/admin/change-password")
    assert r.status_code == 200
    assert b"Change Password" in r.data
