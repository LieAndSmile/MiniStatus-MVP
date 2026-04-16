"""Strategy query param: all / missing = no filter; invalid = no filter."""

from app import create_app
from app.routes.polymarket import _get_strategy


def test_get_strategy_all_and_missing_mean_no_filter():
    app = create_app()
    opts = ["safe_fast", "safe_1to2d_core"]
    with app.test_request_context("/polymarket/portfolio?strategy=all"):
        assert _get_strategy(opts) is None
    with app.test_request_context("/polymarket/portfolio"):
        assert _get_strategy(opts) is None
    with app.test_request_context("/polymarket/portfolio?strategy="):
        assert _get_strategy(opts) is None


def test_get_strategy_known_id_returns_id():
    app = create_app()
    opts = ["safe_fast", "safe_1to2d_core"]
    with app.test_request_context("/polymarket/portfolio?strategy=safe_fast"):
        assert _get_strategy(opts) == "safe_fast"


def test_get_strategy_unknown_returns_none():
    app = create_app()
    opts = ["safe_fast"]
    with app.test_request_context("/polymarket/portfolio?strategy=not_a_real_strategy"):
        assert _get_strategy(opts) is None
