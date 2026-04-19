"""
Test Polymarket Risky tab: template renders with minimal context (no 500).
Run from project root with Flask installed: pytest tests/test_polymarket_risky.py -v
"""
import os
import sys
import pytest

# Project root = parent of tests/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_risky_template_renders_with_minimal_context():
    """Render polymarket_risky.html with minimal context to catch missing vars or template errors."""
    pytest.importorskip("flask")
    from flask import render_template

    os.environ.setdefault("POLYMARKET_DATA_PATH", "/tmp")
    from app import create_app
    app = create_app()

    with app.test_request_context():
        criteria = {"edge_min": 0.01, "gamma_max": 0.94, "expiry_hours_max": 48.0}
        empty_historical = {
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
        context = {
            "configured": True,
            "active_section": "risky",
            "polymarket_sections": [],
            "positions": [],
            "near_risky_positions": [],
            "risky_criteria": criteria,
            "risky_historical": empty_historical,
            "data_freshness": None,
            "total_cost": 0,
            "total_cost_display": "$0",
            "total_unrealized": 0,
            "total_unrealized_display": None,
            "exposure": [],
            "current_days": "all",
            "current_from_date": None,
            "current_sort": "cost_desc",
            "current_strategy": "safe",
            "current_preset": None,
            "risky_presets": {},
            "strategy_options": ["safe"],
            "sort_options": [],
        }
        html = render_template("polymarket_risky.html", **context)
        assert "risky" in html.lower() or "Risky" in html
        assert len(html) > 200
        assert "polymarket-page-header" in html
        assert "Qualifying right now" in html
        assert "Jump:" in html and "#risky-now" in html


def test_risky_empty_state_shows_loose_preset_cta():
    pytest.importorskip("flask")
    from flask import render_template

    os.environ.setdefault("POLYMARKET_DATA_PATH", "/tmp")
    from app import create_app

    app = create_app()
    criteria = {"edge_min": 0.01, "gamma_max": 0.94, "expiry_hours_max": 48.0}
    empty_historical = {
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
    with app.test_request_context("/polymarket/risky"):
        html = render_template(
            "polymarket_risky.html",
            configured=True,
            active_section="risky",
            polymarket_sections=[],
            positions=[],
            near_risky_positions=[],
            risky_criteria=criteria,
            risky_historical=empty_historical,
            data_freshness=None,
            total_cost=0,
            total_cost_display="$0",
            total_unrealized=0,
            total_unrealized_display=None,
            exposure=[],
            current_days="all",
            current_from_date=None,
            current_sort="cost_desc",
            current_strategy="safe",
            current_preset=None,
            risky_presets={},
            strategy_options=["safe"],
            sort_options=[],
            data_quality_flags=[],
        )
    assert "Try looser filter" in html or "preset='loose'" in html
