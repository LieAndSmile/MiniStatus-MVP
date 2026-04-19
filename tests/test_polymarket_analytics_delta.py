"""Task 5b: analytics.prev.json + build_analytics_deltas."""

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.utils.polymarket import (  # noqa: E402
    build_analytics_deltas,
    get_analytics_prev_json,
)


def _write_minimal_data_dir(data_dir):
    """Canonical alerts_log header + empty row so schema validation passes."""
    hdr_path = os.path.join(os.path.dirname(__file__), "fixtures", "alerts_log_header.json")
    with open(hdr_path, "r", encoding="utf-8") as f:
        cols = json.load(f)
    with open(data_dir / "alerts_log.csv", "w", newline="", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
    (data_dir / "open_positions.csv").write_text("question\n", encoding="utf-8")


def test_no_delta_when_prev_missing():
    cur = {
        "totals": {"alerts_resolved": 10},
        "insights": {"drift_status": "active"},
    }
    d = build_analytics_deltas(cur, None, "all")
    assert d["has_prev"] is False


def test_delta_resolved_and_insights_when_prev_present():
    cur = {
        "generated_at": "2026-04-20T12:00:00Z",
        "totals": {"alerts_resolved": 100, "alerts_open": 5},
        "insights": {
            "suggested_edge_threshold": "0.01-0.0125",
            "best_timing_windows": "1-3d",
            "top_strategy_by_roi": "safe_v2",
            "drift_status": "active",
        },
        "strategy_cohort": {
            "safe_v2": {"roi_pct": 3.5},
        },
        "exit_study": {
            "safe_v2": {"2h": {"avg_move": 0.002, "count": 10}},
        },
    }
    prev = {
        "generated_at": "2026-04-19T12:00:00Z",
        "totals": {"alerts_resolved": 95, "alerts_open": 6},
        "insights": {
            "suggested_edge_threshold": "0.0075-0.01",
            "best_timing_windows": "same_day",
            "top_strategy_by_roi": "safe_same_day_core",
            "drift_status": "collecting data",
        },
        "strategy_cohort": {
            "safe_v2": {"roi_pct": 2.0},
        },
        "exit_study": {
            "safe_v2": {"2h": {"avg_move": 0.001, "count": 8}},
        },
    }
    d = build_analytics_deltas(cur, prev, "safe_v2")
    assert d["has_prev"] is True
    assert d["prev_generated_at"] == "2026-04-19T12:00:00Z"
    assert d["totals"]["alerts_resolved"]["delta"] == 5
    assert d["insights"]["drift_status"]["changed"] is True
    assert d["insights"]["drift_status"]["previous"] == "collecting data"
    assert d["cohort_roi_pp"] == pytest.approx(1.5)
    assert d["exit_2h_avg"]["delta"] == pytest.approx(0.001)


def test_get_analytics_prev_json_reads_file(tmp_path):
    prev_path = tmp_path / "analytics.prev.json"
    prev_path.write_text(json.dumps({"generated_at": "x", "totals": {}}), encoding="utf-8")
    loaded = get_analytics_prev_json(str(tmp_path))
    assert loaded is not None
    assert loaded.get("generated_at") == "x"


def test_analytics_page_shows_delta_when_prev_present(tmp_path, monkeypatch):
    from app import create_app

    data_dir = tmp_path / "polydata"
    data_dir.mkdir()
    _write_minimal_data_dir(data_dir)

    cur = {
        "generated_at": "2026-04-20T12:00:00Z",
        "totals": {"alerts_resolved": 100, "alerts_open": 5},
        "insights": {
            "suggested_edge_threshold": "0.01-0.0125",
            "best_timing_windows": "1-3d",
            "top_strategy_by_roi": "safe_v2",
            "drift_status": "active",
        },
        "strategy_cohort": {"safe_v2": {"roi_pct": 3.5}},
        "exit_study": {"safe_v2": {"2h": {"avg_move": 0.002, "count": 10}}},
        "edge_quality": {},
        "timing": {},
    }
    prev = {
        "generated_at": "2026-04-19T12:00:00Z",
        "totals": {"alerts_resolved": 95, "alerts_open": 6},
        "insights": {
            "suggested_edge_threshold": "0.0075-0.01",
            "best_timing_windows": "same_day",
            "top_strategy_by_roi": "safe_same_day_core",
            "drift_status": "collecting data",
        },
        "strategy_cohort": {"safe_v2": {"roi_pct": 2.0}},
        "exit_study": {"safe_v2": {"2h": {"avg_move": 0.001, "count": 8}}},
    }
    (data_dir / "analytics.json").write_text(json.dumps(cur), encoding="utf-8")
    (data_dir / "analytics.prev.json").write_text(json.dumps(prev), encoding="utf-8")

    monkeypatch.setenv("POLYMARKET_DATA_PATH", str(data_dir))
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["authenticated"] = True
        r = c.get("/polymarket/analytics?strategy=safe_v2")
    assert r.status_code == 200
    assert b"vs previous export" in r.data
    assert b"+5" in r.data
    assert b"analytics.prev.json" in r.data


def test_analytics_page_graceful_without_prev(tmp_path, monkeypatch):
    from app import create_app

    data_dir = tmp_path / "polydata"
    data_dir.mkdir()
    _write_minimal_data_dir(data_dir)

    cur = {
        "generated_at": "2026-04-20T12:00:00Z",
        "totals": {"alerts_resolved": 10},
        "insights": {
            "suggested_edge_threshold": "0.01",
            "best_timing_windows": "1-3d",
            "top_strategy_by_roi": "safe_v2",
            "drift_status": "active",
        },
        "edge_quality": {},
        "timing": {},
    }
    (data_dir / "analytics.json").write_text(json.dumps(cur), encoding="utf-8")

    monkeypatch.setenv("POLYMARKET_DATA_PATH", str(data_dir))
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["authenticated"] = True
        r = c.get("/polymarket/analytics")
    assert r.status_code == 200
    assert b"At a glance" in r.data
    assert b"analytics.prev.json" not in r.data
