"""Smoke: secondary Polymarket pages render the shared page header partial."""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.mark.parametrize(
    "path",
    [
        "/polymarket/risky",
        "/polymarket/loss-lab",
        "/polymarket/analytics",
        "/polymarket/ai-performance",
        "/polymarket/ai-simulation",
    ],
)
def test_polymarket_secondary_pages_include_shared_header(path, tmp_path, monkeypatch):
    import json

    from app import create_app

    data_dir = tmp_path / "polydata"
    data_dir.mkdir()
    # Minimal canonical header (schema validation)
    hdr_path = os.path.join(os.path.dirname(__file__), "fixtures", "alerts_log_header.json")
    with open(hdr_path, "r", encoding="utf-8") as f:
        cols = json.load(f)
    with open(data_dir / "alerts_log.csv", "w", newline="", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
    (data_dir / "open_positions.csv").write_text("question\n", encoding="utf-8")

    monkeypatch.setenv("POLYMARKET_DATA_PATH", str(data_dir))

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["authenticated"] = True
        r = c.get(path)
    assert r.status_code == 200
    assert b"polymarket-page-header" in r.data
