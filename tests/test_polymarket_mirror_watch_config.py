"""mirror_watch_config.json read/write for Mirror alerts tab."""
import json
import tempfile

from app.utils.polymarket import get_mirror_watch_config, save_mirror_watch_config, MIRROR_WATCH_MAX_WALLETS


def test_save_and_load_roundtrip():
    d = tempfile.mkdtemp()
    ok, err = save_mirror_watch_config(
        d,
        {
            "wallets": [
                {
                    "id": "a",
                    "address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "label": "One",
                    "telegram_enabled": True,
                }
            ]
        },
    )
    assert ok and not err
    cfg = get_mirror_watch_config(d)
    assert cfg["wallets"][0]["address"] == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert cfg["wallets"][0]["telegram_enabled"] is True
    assert cfg["wallets"][0]["poll_group"] == "standard"


def test_save_poll_group_fast_roundtrip():
    d = tempfile.mkdtemp()
    ok, err = save_mirror_watch_config(
        d,
        {
            "wallets": [
                {
                    "id": "b",
                    "address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "label": "Fast",
                    "telegram_enabled": True,
                    "poll_group": "fast",
                }
            ]
        },
    )
    assert ok and not err
    cfg = get_mirror_watch_config(d)
    assert cfg["wallets"][0]["poll_group"] == "fast"


def test_rejects_bad_address():
    d = tempfile.mkdtemp()
    ok, _ = save_mirror_watch_config(
        d,
        {"wallets": [{"address": "not-an-address", "label": "x", "telegram_enabled": True}]},
    )
    assert ok
    cfg = get_mirror_watch_config(d)
    assert cfg["wallets"] == []
