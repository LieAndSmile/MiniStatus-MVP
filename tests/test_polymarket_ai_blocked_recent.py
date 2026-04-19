"""Unit tests for get_recent_ai_blocked helper."""

import csv
import os
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.utils.polymarket import get_recent_ai_blocked  # noqa: E402


def test_get_recent_ai_blocked_returns_at_most_5():
    rows = [
        {
            "ts": "2026-01-0%dT12:00:00Z" % i,
            "question": "Q%d?" % i,
            "strategy_id": "s_a",
            "ai_verdict": "SKIP",
            "ai_applied_effect": "skip_high",
            "resolved": "true",
            "actual_result": "NO",
            "pnl_usd": "0",
            "status": "sent",
        }
        for i in range(1, 10)
    ]
    header = list(rows[0].keys())
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "alerts_log.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            w.writerows(rows)
        out = get_recent_ai_blocked(td, limit=5, strategy=None)
        assert len(out) == 5
        # Newest first: Jan-09 down to Jan-05
        assert "Q9?" in out[0]["question"] or out[0]["question"].startswith("Q9")


def test_get_recent_ai_blocked_respects_strategy_filter():
    rows = [
        {
            "ts": "2026-02-01T12:00:00Z",
            "question": "A?",
            "strategy_id": "s_one",
            "ai_verdict": "SKIP",
            "ai_applied_effect": "skip_high",
            "resolved": "true",
            "actual_result": "NO",
            "pnl_usd": "0",
            "status": "sent",
        },
        {
            "ts": "2026-02-02T12:00:00Z",
            "question": "B?",
            "strategy_id": "s_two",
            "ai_verdict": "SKIP",
            "ai_applied_effect": "skip_med",
            "resolved": "true",
            "actual_result": "YES",
            "pnl_usd": "0",
            "status": "sent",
        },
    ]
    header = list(rows[0].keys())
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "alerts_log.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            w.writerows(rows)
        one = get_recent_ai_blocked(td, limit=5, strategy="s_one")
        assert len(one) == 1
        assert one[0]["strategy_id"] == "s_one"
