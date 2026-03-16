import os

import pytest


@pytest.mark.skipif(
    "POLYMARKET_DATA_PATH" not in os.environ,
    reason="POLYMARKET_DATA_PATH not set in test environment",
)
def test_polymarket_health_smoke():
    """
    Smoke-test Polymarket health helpers and routes.

    This does not assert specific ages or schema details – only that the
    helpers can be imported and the JSON endpoints respond with 200.
    """
    from app import create_app  # noqa: F401
    from app.utils.polymarket_health import (  # noqa: F401
        get_polymarket_health,
        get_polymarket_freshness,
    )

    app = create_app()
    client = app.test_client()

    # Health endpoint should always return 200 with JSON
    resp = client.get("/polymarket/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    assert "configured" in data
    assert "freshness" in data

    # Freshness endpoint should also return 200 with JSON
    resp2 = client.get("/polymarket/freshness")
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert isinstance(data2, dict)
    assert "configured" in data2
    assert "freshness" in data2

