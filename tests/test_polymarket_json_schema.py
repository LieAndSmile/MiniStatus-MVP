"""JSON artifact schema_version handling (producer vs dashboard support)."""
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest


def test_collect_schema_warnings_empty_when_missing_files(tmp_path):
    from app.utils.polymarket import collect_json_artifact_schema_warnings

    assert collect_json_artifact_schema_warnings(str(tmp_path)) == []


def test_collect_schema_warnings_when_newer_than_dashboard(tmp_path, monkeypatch):
    from app.utils import polymarket_constants as pc
    from app.utils.polymarket import collect_json_artifact_schema_warnings

    monkeypatch.setattr(pc, "SUPPORTED_JSON_ARTIFACT_SCHEMA_VERSION", 1)
    (tmp_path / "analytics.json").write_text(
        json.dumps({"schema_version": 99, "generated_at": "2026-01-01T00:00:00Z", "totals": {}}),
        encoding="utf-8",
    )
    w = collect_json_artifact_schema_warnings(str(tmp_path))
    assert len(w) == 1
    assert "analytics.json" in w[0]
    assert "99" in w[0]


def test_collect_schema_warnings_legacy_no_version_ok(tmp_path):
    from app.utils.polymarket import collect_json_artifact_schema_warnings

    (tmp_path / "lifecycle.json").write_text(
        json.dumps({"generated_at": "2026-01-01T00:00:00Z", "strategies": {}}),
        encoding="utf-8",
    )
    assert collect_json_artifact_schema_warnings(str(tmp_path)) == []
