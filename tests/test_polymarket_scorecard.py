"""Chunk 1a: get_strategy_scorecard(); Chunk 1b: /polymarket/scorecard JSON route."""
import csv
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app  # noqa: E402
from app.utils.polymarket import get_strategy_scorecard  # noqa: E402


MIN_FIELDS = [
    "ts",
    "question",
    "status",
    "strategy_id",
    "resolved",
    "actual_result",
    "pnl_usd",
    "cost_usd",
    "bet_size_usd",
    "sport",
]


def _write_csv(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MIN_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in MIN_FIELDS})


def test_empty_csv_returns_empty_list(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_csv(str(data_dir / "alerts_log.csv"), [])
    assert get_strategy_scorecard(str(data_dir)) == []


def test_one_sent_resolved_row_aggregates(tmp_path):
    data_dir = tmp_path / "data"
    _write_csv(
        str(data_dir / "alerts_log.csv"),
        [
            {
                "ts": "2026-04-10T10:00:00Z",
                "question": "Q1",
                "status": "sent",
                "strategy_id": "safe_same_day_core",
                "resolved": "true",
                "actual_result": "YES",
                "pnl_usd": "50",
                "cost_usd": "100",
                "bet_size_usd": "",
                "sport": "nba",
            },
        ],
    )
    rows = get_strategy_scorecard(str(data_dir), safe_scope="all_tracked")
    assert len(rows) == 1
    r = rows[0]
    assert r["strategy_id"] == "safe_same_day_core"
    assert r["sent"] == 1
    assert r["resolved"] == 1
    assert r["wins"] == 1
    assert r["losses"] == 0
    assert r["win_rate"] == pytest.approx(1.0)
    assert r["realized_pnl_usd"] == 50.0
    assert r["cost_usd_total"] == 100.0
    assert r["roi_pct"] == pytest.approx(0.5)
    assert r["sample_warning"] is True
    assert "2026-04-10" in r["last_sent_ts"]


def test_unresolved_sent_counts_sent_not_resolved(tmp_path):
    data_dir = tmp_path / "data"
    _write_csv(
        str(data_dir / "alerts_log.csv"),
        [
            {
                "ts": "2026-04-10T10:00:00Z",
                "question": "Q1",
                "status": "sent",
                "strategy_id": "safe_same_day_core",
                "resolved": "false",
                "actual_result": "",
                "pnl_usd": "",
                "cost_usd": "10",
                "bet_size_usd": "",
                "sport": "nba",
            },
        ],
    )
    rows = get_strategy_scorecard(str(data_dir), safe_scope="all_tracked")
    assert rows[0]["sent"] == 1
    assert rows[0]["resolved"] == 0
    assert rows[0]["wins"] == 0
    assert rows[0]["losses"] == 0
    assert rows[0]["win_rate"] == 0.0


def test_safe_only_filters_non_allowlist_sports(tmp_path):
    import app.utils.polymarket as pm

    # Default allowlist (soccer, tennis, nba, nhl, ml b) — excludes esports, mma, other
    _write_csv(
        str(tmp_path / "alerts_log.csv"),
        [
            {
                "ts": "2026-04-10T10:00:00Z",
                "question": "A",
                "status": "sent",
                "strategy_id": "s1",
                "resolved": "true",
                "pnl_usd": "1",
                "cost_usd": "1",
                "bet_size_usd": "",
                "sport": "esports",
            },
            {
                "ts": "2026-04-10T11:00:00Z",
                "question": "B",
                "status": "sent",
                "strategy_id": "s2",
                "resolved": "true",
                "pnl_usd": "2",
                "cost_usd": "1",
                "bet_size_usd": "",
                "sport": "mma",
            },
            {
                "ts": "2026-04-10T12:00:00Z",
                "question": "C",
                "status": "sent",
                "strategy_id": "s3",
                "resolved": "true",
                "pnl_usd": "3",
                "cost_usd": "1",
                "bet_size_usd": "",
                "sport": "other",
            },
            {
                "ts": "2026-04-10T13:00:00Z",
                "question": "D",
                "status": "sent",
                "strategy_id": "ok",
                "resolved": "true",
                "pnl_usd": "10",
                "cost_usd": "5",
                "bet_size_usd": "",
                "sport": "nba",
            },
        ],
    )
    pm._CSV_CACHE.clear()
    rows = get_strategy_scorecard(str(tmp_path), safe_scope="safe_only")
    assert len(rows) == 1
    assert rows[0]["strategy_id"] == "ok"


def test_days_filter_respects_ts_cutoff(tmp_path):
    import app.utils.polymarket as pm

    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = (now - timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_csv(
        str(tmp_path / "alerts_log.csv"),
        [
            {
                "ts": old,
                "question": "Old",
                "status": "sent",
                "strategy_id": "old_s",
                "resolved": "true",
                "pnl_usd": "99",
                "cost_usd": "1",
                "bet_size_usd": "",
                "sport": "nba",
            },
            {
                "ts": recent,
                "question": "New",
                "status": "sent",
                "strategy_id": "new_s",
                "resolved": "true",
                "pnl_usd": "1",
                "cost_usd": "1",
                "bet_size_usd": "",
                "sport": "nba",
            },
        ],
    )
    pm._CSV_CACHE.clear()
    rows = get_strategy_scorecard(str(tmp_path), safe_scope="all_tracked", days=7)
    assert len(rows) == 1
    assert rows[0]["strategy_id"] == "new_s"


def test_sample_warning_when_resolved_lt_30(tmp_path):
    import app.utils.polymarket as pm

    rows_in = [
        {
            "ts": f"2026-04-{i+1:02d}T10:00:00Z",
            "question": f"Q{i}",
            "status": "sent",
            "strategy_id": "heavy",
            "resolved": "true",
            "pnl_usd": "1",
            "cost_usd": "1",
            "bet_size_usd": "",
            "sport": "nba",
        }
        for i in range(29)
    ]
    _write_csv(str(tmp_path / "alerts_log.csv"), rows_in)
    pm._CSV_CACHE.clear()
    rows = get_strategy_scorecard(str(tmp_path), safe_scope="all_tracked")
    assert len(rows) == 1
    assert rows[0]["resolved"] == 29
    assert rows[0]["sample_warning"] is True

    rows_in30 = rows_in + [
        {
            "ts": "2026-04-30T10:00:00Z",
            "question": "Q30",
            "status": "sent",
            "strategy_id": "heavy",
            "resolved": "true",
            "pnl_usd": "1",
            "cost_usd": "1",
            "bet_size_usd": "",
            "sport": "nba",
        },
    ]
    _write_csv(str(tmp_path / "alerts_log.csv"), rows_in30)
    pm._CSV_CACHE.clear()
    rows2 = get_strategy_scorecard(str(tmp_path), safe_scope="all_tracked")
    assert rows2[0]["resolved"] == 30
    assert rows2[0]["sample_warning"] is False


def test_sorted_by_realized_pnl_desc(tmp_path):
    import app.utils.polymarket as pm

    _write_csv(
        str(tmp_path / "alerts_log.csv"),
        [
            {
                "ts": "2026-04-10T10:00:00Z",
                "question": "a",
                "status": "sent",
                "strategy_id": "low",
                "resolved": "true",
                "pnl_usd": "5",
                "cost_usd": "1",
                "bet_size_usd": "",
                "sport": "nba",
            },
            {
                "ts": "2026-04-10T11:00:00Z",
                "question": "b",
                "status": "sent",
                "strategy_id": "high",
                "resolved": "true",
                "pnl_usd": "100",
                "cost_usd": "1",
                "bet_size_usd": "",
                "sport": "nba",
            },
        ],
    )
    pm._CSV_CACHE.clear()
    rows = get_strategy_scorecard(str(tmp_path), safe_scope="all_tracked")
    assert [r["strategy_id"] for r in rows] == ["high", "low"]


def test_scorecard_route_redirects_when_not_authenticated(tmp_path, monkeypatch):
    monkeypatch.setenv("POLYMARKET_DATA_PATH", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        r = c.get("/polymarket/scorecard")
    assert r.status_code == 302
    assert "/admin/login" in (r.headers.get("Location") or "")


def test_scorecard_json_route(tmp_path, monkeypatch):
    import app.utils.polymarket as pm

    monkeypatch.setenv("POLYMARKET_DATA_PATH", str(tmp_path))
    _write_csv(
        str(tmp_path / "alerts_log.csv"),
        [
            {
                "ts": "2026-04-10T10:00:00Z",
                "question": "Q",
                "status": "sent",
                "strategy_id": "s_a",
                "resolved": "true",
                "pnl_usd": "10",
                "cost_usd": "5",
                "bet_size_usd": "",
                "sport": "nba",
            },
        ],
    )
    pm._CSV_CACHE.clear()
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["authenticated"] = True
        r = c.get("/polymarket/scorecard?format=json&safe_scope=all_tracked")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["strategy_id"] == "s_a"
    assert data[0]["realized_pnl_usd"] == 10.0


def test_scorecard_html_renders(tmp_path, monkeypatch):
    import app.utils.polymarket as pm

    monkeypatch.setenv("POLYMARKET_DATA_PATH", str(tmp_path))
    _write_csv(
        str(tmp_path / "alerts_log.csv"),
        [
            {
                "ts": "2026-04-10T10:00:00Z",
                "question": "Q",
                "status": "sent",
                "strategy_id": "s_a",
                "resolved": "true",
                "pnl_usd": "10",
                "cost_usd": "5",
                "bet_size_usd": "",
                "sport": "nba",
            },
        ],
    )
    pm._CSV_CACHE.clear()
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["authenticated"] = True
        r = c.get("/polymarket/scorecard")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Strategy scorecard" in html
    assert "s_a" in html or "S_a" in html  # label or raw id


def test_polymarket_safe_scope_persists_in_session(tmp_path, monkeypatch):
    """Phase 5a: choosing scope on scorecard stores session default for later requests."""
    import app.utils.polymarket as pm

    monkeypatch.setenv("POLYMARKET_DATA_PATH", str(tmp_path))
    _write_csv(
        str(tmp_path / "alerts_log.csv"),
        [
            {
                "ts": "2026-04-10T10:00:00Z",
                "question": "Q",
                "status": "sent",
                "strategy_id": "s_a",
                "resolved": "true",
                "pnl_usd": "10",
                "cost_usd": "5",
                "bet_size_usd": "",
                "sport": "nba",
            },
        ],
    )
    pm._CSV_CACHE.clear()
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["authenticated"] = True
        c.get("/polymarket/scorecard?safe_scope=all_tracked&format=html")
        with c.session_transaction() as sess:
            assert sess.get("polymarket_safe_scope") == "all_tracked"


def test_scorecard_defaults_to_html_json_explicit(tmp_path, monkeypatch):
    """Default format is HTML; ``format=json`` still returns JSON."""
    import app.utils.polymarket as pm

    monkeypatch.setenv("POLYMARKET_DATA_PATH", str(tmp_path))
    _write_csv(str(tmp_path / "alerts_log.csv"), [])
    pm._CSV_CACHE.clear()
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["authenticated"] = True
        r_html = c.get("/polymarket/scorecard")
        r_json = c.get("/polymarket/scorecard?format=json")
    assert r_html.status_code == 200
    assert b"Strategy scorecard" in r_html.data
    assert r_json.status_code == 200
    assert r_json.get_json() == []


def test_polymarket_primary_nav_four_tabs():
    """Phase 5b: horizontal Polymarket nav is four primary tabs + Tools hub for the rest."""
    from app.routes.polymarket import POLYMARKET_OPS_ENDPOINTS, POLYMARKET_SECTIONS

    assert len(POLYMARKET_SECTIONS) == 4
    assert [s[0] for s in POLYMARKET_SECTIONS] == ["portfolio", "scorecard", "ai-simulation", "ops"]
    assert "polymarket.polymarket_analytics" in POLYMARKET_OPS_ENDPOINTS


def test_polymarket_ops_hub_renders(tmp_path, monkeypatch):
    """GET /polymarket/ops renders the secondary-tools hub."""
    import app.utils.polymarket as pm

    monkeypatch.setenv("POLYMARKET_DATA_PATH", str(tmp_path))
    _write_csv(str(tmp_path / "alerts_log.csv"), [])
    pm._CSV_CACHE.clear()
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["authenticated"] = True
        r = c.get("/polymarket/ops")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Open Positions" in html
    assert "Analytics" in html
