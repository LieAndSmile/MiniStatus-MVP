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
import tempfile

import pytest


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
