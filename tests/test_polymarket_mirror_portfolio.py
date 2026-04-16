"""Mirror Portfolio JSON loader for MiniStatus."""
import json
import os

import pytest

from app.utils.polymarket import get_mirror_portfolio_json, get_mirror_portfolio_file_age


def test_get_mirror_portfolio_json_missing(tmp_path):
    assert get_mirror_portfolio_json(str(tmp_path)) is None


def test_get_mirror_portfolio_json_loads(tmp_path):
    payload = {
        "meta": {"wallet": "0xabc", "schema_version": 1},
        "summary": {"realized_usdc": 1.5},
        "ledger": [],
        "open_positions": [],
        "resolution_events": [],
        "anomalies": [],
    }
    p = tmp_path / "mirror_portfolio.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    d = get_mirror_portfolio_json(str(tmp_path))
    assert d is not None
    assert d["meta"]["wallet"] == "0xabc"
    assert d["summary"]["realized_usdc"] == 1.5


def test_get_mirror_portfolio_file_age(tmp_path):
    p = tmp_path / "mirror_portfolio.json"
    p.write_text("{}", encoding="utf-8")
    age = get_mirror_portfolio_file_age(str(tmp_path))
    assert age is not None
    assert "ago" in age or "just now" in age
