"""
Lock MiniStatus CSV expectations to polymarket-alerts canonical header.

`tests/fixtures/alerts_log_header.json` must match:
  polymarket-alerts/docs/alerts_log_header.json

Regenerate the producer file after ALERTS_HEADER changes, then copy here.
See polymarket-alerts/docs/INTEGRATION_CONTRACT.md — Schema change checklist.
"""

import csv
import json
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture
def canonical_header():
    root = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(root, "fixtures", "alerts_log_header.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_fixture_matches_polymarket_export_shape(canonical_header):
    assert isinstance(canonical_header, list)
    assert canonical_header[0] == "alert_id"
    assert "question" in canonical_header
    assert "pnl_usd" in canonical_header
    assert canonical_header[-1] == "ai_applied_effect"


def test_validate_alerts_log_schema_accepts_canonical_header(canonical_header):
    from app.utils.polymarket import validate_alerts_log_schema

    row = {c: "" for c in canonical_header}
    row["ts"] = "2026-01-01T00:00:00Z"
    row["question"] = "fixture schema smoke"
    row["resolved"] = "false"
    row["actual_result"] = ""
    row["pnl_usd"] = ""

    with tempfile.TemporaryDirectory() as d:
        csv_path = os.path.join(d, "alerts_log.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=canonical_header)
            w.writeheader()
            w.writerow(row)
        ok, err = validate_alerts_log_schema(d)
        assert ok, err


def test_data_quality_skips_analytics_warning_when_alerts_schema_invalid(tmp_path):
    """Broken alerts_log must not show the analytics.json drift banner (misleading)."""
    from app.utils.polymarket_health import get_data_quality_flags

    bad_csv = tmp_path / "alerts_log.csv"
    bad_csv.write_text("x\n1\n", encoding="utf-8")
    aj = tmp_path / "analytics.json"
    aj.write_text(
        '{"strategy_cohort": {"s": {"resolved_count": 28}}}',
        encoding="utf-8",
    )
    flags = get_data_quality_flags(str(tmp_path))
    messages = [f.get("message", "") for f in flags]
    assert not any("analytics.json still shows" in m for m in messages)


def test_data_quality_analytics_warning_when_schema_ok_csv_empty(tmp_path, canonical_header):
    """When schema is valid but CSV has no sent+resolved rows, drift banner is appropriate."""
    from app.utils.polymarket_health import get_data_quality_flags

    row = {c: "" for c in canonical_header}
    row["ts"] = "2026-01-01T00:00:00Z"
    row["question"] = "q"
    row["resolved"] = "false"
    row["actual_result"] = ""
    row["pnl_usd"] = ""
    row["status"] = "sent"

    csv_path = tmp_path / "alerts_log.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=canonical_header)
        w.writeheader()
        w.writerow(row)
    aj = tmp_path / "analytics.json"
    aj.write_text(
        '{"strategy_cohort": {"s": {"resolved_count": 28}}}',
        encoding="utf-8",
    )
    flags = get_data_quality_flags(str(tmp_path))
    assert any("analytics.json still shows" in f.get("message", "") for f in flags)
