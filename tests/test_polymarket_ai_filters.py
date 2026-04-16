import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _write_alerts_csv(data_dir: str, extra_rows: list | None = None):
    path = os.path.join(data_dir, "alerts_log.csv")
    fieldnames = [
        "ts", "question", "status", "strategy_id", "resolved", "actual_result",
        "pnl_usd", "resolved_ts", "ai_verdict", "ai_confidence", "ai_red_flags",
        "sport", "market_type", "link", "bet_size_usd", "cost_usd",
        "gamma", "best_ask", "yes_price", "effective", "edge",
        "primary_block_reason",
    ]
    rows = [
        {
            "ts": "2026-03-31T10:00:00Z",
            "question": "Q safe",
            "status": "ai_sim",
            "strategy_id": "safe_fast",
            "resolved": "true",
            "actual_result": "YES",
            "pnl_usd": "12.5",
            "resolved_ts": "2026-03-31T11:00:00Z",
            "ai_verdict": "BET",
            "ai_confidence": "High",
            "ai_red_flags": "",
            "sport": "crypto",
            "market_type": "binary",
            "link": "https://polymarket.com/market/q-safe",
            "bet_size_usd": "100",
            "cost_usd": "100",
            "gamma": "0.9",
            "best_ask": "0.89",
            "yes_price": "0.89",
            "effective": "0.9",
            "edge": "0.01",
            "primary_block_reason": "",
        },
        {
            "ts": "2026-03-31T10:30:00Z",
            "question": "Q probe",
            "status": "ai_sim",
            "strategy_id": "gamma_86_92_probe",
            "resolved": "true",
            "actual_result": "NO",
            "pnl_usd": "-10.0",
            "resolved_ts": "2026-03-31T12:00:00Z",
            "ai_verdict": "BET",
            "ai_confidence": "Medium",
            "ai_red_flags": "headline risk",
            "sport": "politics",
            "market_type": "binary",
            "link": "https://polymarket.com/market/q-probe",
            "bet_size_usd": "50",
            "cost_usd": "50",
            "gamma": "0.88",
            "best_ask": "0.87",
            "yes_price": "0.87",
            "effective": "0.88",
            "edge": "0.005",
            "primary_block_reason": "",
        },
    ]
    if extra_rows:
        rows.extend(extra_rows)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _blocked_row(actual_result: str, best_ask: str = "0.75") -> dict:
    return {
        "ts": "2026-03-31T09:00:00Z",
        "question": "Q blocked",
        "status": "blocked_ai_screen",
        "strategy_id": "safe_fast",
        "resolved": "true",
        "actual_result": actual_result,
        "pnl_usd": "0.00",
        "resolved_ts": "2026-04-01T10:00:00Z",
        "ai_verdict": "SKIP",
        "ai_confidence": "High",
        "ai_red_flags": "vague_question|thin_market",
        "sport": "soccer",
        "market_type": "binary",
        "link": "https://polymarket.com/market/q-blocked",
        "bet_size_usd": "",
        "cost_usd": "",
        "gamma": "0.88",
        "best_ask": best_ask,
        "yes_price": best_ask,
        "effective": "",
        "edge": "",
        "primary_block_reason": "AI_SKIP_HIGH: Too much lineup uncertainty",
    }


def _sent_row(actual_result: str) -> dict:
    return {
        "ts": "2026-03-30T10:00:00Z",
        "question": "Q sent",
        "status": "sent",
        "strategy_id": "safe_fast",
        "resolved": "true",
        "actual_result": actual_result,
        "pnl_usd": "20.0" if actual_result == "YES" else "-50.0",
        "resolved_ts": "2026-03-31T10:00:00Z",
        "ai_verdict": "BET",
        "ai_confidence": "Medium",
        "ai_red_flags": "",
        "sport": "other",
        "market_type": "binary",
        "link": "",
        "bet_size_usd": "100",
        "cost_usd": "100",
        "gamma": "0.90",
        "best_ask": "0.88",
        "yes_price": "0.88",
        "effective": "0.89",
        "edge": "0.02",
        "primary_block_reason": "",
    }


# ── Existing tests (updated assertions) ─────────────────────────────────────

def test_get_ai_sim_stats_respects_strategy_filter(tmp_path):
    from app.utils.polymarket import get_ai_sim_stats

    _write_alerts_csv(str(tmp_path))
    stats = get_ai_sim_stats(str(tmp_path), strategy="safe_fast")
    assert stats is not None
    assert stats["alerts_total"] == 1
    assert len(stats["resolved_list"]) == 1
    assert stats["resolved_list"][0]["strategy_id"] == "safe_fast"


def test_get_ai_performance_respects_strategy_filter(tmp_path):
    from app.utils.polymarket import get_ai_performance

    _write_alerts_csv(str(tmp_path))
    perf = get_ai_performance(str(tmp_path), strategy="safe_fast")
    assert perf["total_screened"] == 1
    assert len(perf["accuracy_tiers"]) == 1
    assert perf["accuracy_tiers"][0]["verdict"] == "BET"
    # New shape: correct/wrong/accuracy_pct instead of wins/losses/hit_rate
    tier = perf["accuracy_tiers"][0]
    assert "correct" in tier
    assert "wrong" in tier
    assert "accuracy_pct" in tier
    assert "wins" not in tier
    assert "losses" not in tier
    assert "hit_rate" not in tier


# ── New tests: direction-based SKIP accuracy ─────────────────────────────────

def test_skip_correctness_direction_based(tmp_path):
    """SKIP correct=NO, wrong=YES — never uses pnl_usd."""
    from app.utils.polymarket import get_ai_performance

    _write_alerts_csv(str(tmp_path), extra_rows=[
        _blocked_row("NO"),   # correct: avoided a loss
        _blocked_row("YES"),  # wrong: missed a winner
    ])
    perf = get_ai_performance(str(tmp_path))
    skip_tier = next((t for t in perf["accuracy_tiers"] if t["verdict"] == "SKIP"), None)
    assert skip_tier is not None, "SKIP tier missing"
    assert skip_tier["correct"] == 1
    assert skip_tier["wrong"] == 1
    assert skip_tier["accuracy_pct"] == 50.0


def test_skip_cf_pnl_calculation(tmp_path):
    """Counterfactual P/L: correct SKIP saves CF_STANDARD_BET; wrong SKIP costs (CF_BET/entry - CF_BET)."""
    from app.utils.polymarket import get_ai_performance, _CF_STANDARD_BET

    entry = 0.5  # best_ask
    _write_alerts_csv(str(tmp_path), extra_rows=[
        _blocked_row("NO", best_ask=str(entry)),   # correct → +100
        _blocked_row("YES", best_ask=str(entry)),  # wrong   → -(100*(1/0.5-1)) = -100
    ])
    perf = get_ai_performance(str(tmp_path))
    skip_tier = next(t for t in perf["accuracy_tiers"] if t["verdict"] == "SKIP")
    # Net: +100 - 100 = 0
    assert skip_tier["cf_pnl_saved"] == 0.0
    # Blocked row entries
    blocked = perf["blocked_rows"]
    assert len(blocked) == 2
    correct_row = next(b for b in blocked if b["outcome_verdict"] == "correct")
    wrong_row = next(b for b in blocked if b["outcome_verdict"] == "wrong")
    assert correct_row["cf_pnl_est"] == _CF_STANDARD_BET
    assert wrong_row["cf_pnl_est"] == -_CF_STANDARD_BET  # entry=0.5 → opp cost = 100


def test_skip_pending_when_unresolved(tmp_path):
    """Unresolved SKIP rows count as pending (not correct or wrong)."""
    from app.utils.polymarket import get_ai_performance

    unresolved = _blocked_row("")
    unresolved["resolved"] = "true"   # resolved flag set but actual_result is blank
    _write_alerts_csv(str(tmp_path), extra_rows=[unresolved])
    perf = get_ai_performance(str(tmp_path))
    skip_tier = next((t for t in perf["accuracy_tiers"] if t["verdict"] == "SKIP"), None)
    # Row is resolved but has no actual_result — should not appear in tiers
    # (is_resolved check requires actual in YES/NO or resolved=true; blank actual_result → still resolved=true)
    # pending = resolved - correct - wrong
    if skip_tier:
        assert skip_tier["correct"] == 0
        assert skip_tier["wrong"] == 0


def test_baseline_loss_rate_computed(tmp_path):
    """baseline_loss_rate is the fraction of sent rows that resolved NO."""
    from app.utils.polymarket import get_ai_performance

    _write_alerts_csv(str(tmp_path), extra_rows=[
        _sent_row("YES"),
        _sent_row("NO"),
        _sent_row("NO"),
    ])
    # Base rows: 1 sent YES (from ai_sim fixture — but ai_sim not counted, only "sent")
    # Extra: 1 YES + 2 NO → 3 sent resolved, 2 losses → 66.7%
    perf = get_ai_performance(str(tmp_path))
    assert perf["baseline_loss_rate"] is not None
    assert isinstance(perf["baseline_loss_rate"], float)
    assert perf["baseline_loss_rate"] == pytest.approx(66.7, abs=0.1)


def test_bet_accuracy_direction_based(tmp_path):
    """BET verdict: correct if YES, wrong if NO (not pnl-sign)."""
    from app.utils.polymarket import get_ai_performance

    _write_alerts_csv(str(tmp_path))
    perf = get_ai_performance(str(tmp_path))
    # safe_fast row: BET High, actual=YES → correct
    tier = next(t for t in perf["accuracy_tiers"] if t["verdict"] == "BET" and t["confidence"] == "High")
    assert tier["correct"] == 1
    assert tier["wrong"] == 0
    assert tier["accuracy_pct"] == 100.0
    # gamma_86 row: BET Medium, actual=NO → wrong
    tier2 = next(t for t in perf["accuracy_tiers"] if t["verdict"] == "BET" and t["confidence"] == "Medium")
    assert tier2["correct"] == 0
    assert tier2["wrong"] == 1
    assert tier2["accuracy_pct"] == 0.0


def test_return_dict_has_new_keys(tmp_path):
    """Return dict includes baseline_loss_rate and cf_standard_bet."""
    from app.utils.polymarket import get_ai_performance

    _write_alerts_csv(str(tmp_path))
    perf = get_ai_performance(str(tmp_path))
    assert "baseline_loss_rate" in perf
    assert "cf_standard_bet" in perf
    assert perf["cf_standard_bet"] == 100.0
    assert "lift_metrics" in perf
    assert perf["data_source"] == "csv"
    assert perf["ai_loop_display_source"] == "none"


def test_get_ai_performance_uses_fresh_artifact(tmp_path):
    import json

    from app.utils.polymarket import get_ai_performance

    _write_alerts_csv(str(tmp_path))
    csv_path = os.path.join(str(tmp_path), "alerts_log.csv")
    csv_m = os.path.getmtime(csv_path)

    perf_stub = {
        "has_data": True,
        "accuracy_tiers": [],
        "blocked_rows": [],
        "blocked_rows_full_count": 0,
        "total_screened": 4242,
        "total_blocked": 0,
        "overall_accuracy": None,
        "baseline_loss_rate": None,
        "cf_standard_bet": 100.0,
        "lift_metrics": {
            "false_block_rate_pct": None,
            "loss_avoided_rate_pct": None,
            "blocked_judged_count": 0,
            "counterfactual_blocked_pnl_est": None,
            "baseline_loss_rate_pct": None,
            "skip_tier_lift_pp": None,
        },
    }
    art = {
        "schema_version": 1,
        "exported_at": "2026-01-01T00:00:00+00:00",
        "freshness": {"alerts_log_csv_mtime": csv_m},
        "producer": {"global_ai_policy": "advisory"},
        "performance": perf_stub,
        "sim": {"open_list": [], "resolved_list": []},
    }
    with open(os.path.join(str(tmp_path), "ai_performance.json"), "w", encoding="utf-8") as f:
        json.dump(art, f)

    out = get_ai_performance(str(tmp_path), strategy="all")
    assert out["data_source"] == "artifact"
    assert out["total_screened"] == 4242
    assert out["producer_global_ai_policy"] == "advisory"
    assert out["ai_loop_display_source"] == "artifact_snapshot"


def test_ai_loop_state_live_overrides_artifact_producer(tmp_path):
    """Phase 3: live ai_loop_state.json wins over embedded export producer fields."""
    import json

    from app.utils.polymarket import get_ai_performance

    _write_alerts_csv(str(tmp_path))
    csv_path = os.path.join(str(tmp_path), "alerts_log.csv")
    csv_m = os.path.getmtime(csv_path)
    perf_stub = {
        "has_data": True,
        "accuracy_tiers": [],
        "blocked_rows": [],
        "blocked_rows_full_count": 0,
        "total_screened": 100,
        "total_blocked": 0,
        "overall_accuracy": None,
        "baseline_loss_rate": None,
        "cf_standard_bet": 100.0,
        "lift_metrics": {
            "false_block_rate_pct": None,
            "loss_avoided_rate_pct": None,
            "blocked_judged_count": 0,
            "counterfactual_blocked_pnl_est": None,
            "baseline_loss_rate_pct": None,
            "skip_tier_lift_pp": None,
        },
    }
    art = {
        "schema_version": 1,
        "exported_at": "2026-01-01T00:00:00+00:00",
        "freshness": {"alerts_log_csv_mtime": csv_m},
        "producer": {
            "global_ai_policy": "shadow",
            "counters": {"ai_skip_count": 1},
        },
        "performance": perf_stub,
        "sim": {"open_list": [], "resolved_list": []},
    }
    with open(os.path.join(str(tmp_path), "ai_performance.json"), "w", encoding="utf-8") as f:
        json.dump(art, f)

    loop_state = {
        "schema_version": 1,
        "global_ai_policy": "advisory",
        "allow_hard_block": False,
        "counters": {"ai_skip_count": 500},
        "updated_at": "2026-04-13T12:00:00Z",
        "last_ai_screen_ts": "2026-04-13T11:00:00Z",
    }
    with open(os.path.join(str(tmp_path), "ai_loop_state.json"), "w", encoding="utf-8") as f:
        json.dump(loop_state, f)

    out = get_ai_performance(str(tmp_path), strategy="all")
    assert out["data_source"] == "artifact"
    assert out["total_screened"] == 100
    assert out["producer_global_ai_policy"] == "advisory"
    assert out["producer_counters"]["ai_skip_count"] == 500
    assert out["ai_loop_display_source"] == "live"
    assert any(r["key"] == "ai_skip_count" and r["value"] == 500 for r in out["producer_counter_rows"])


def test_producer_last_screen_meta_from_live_loop_state(tmp_path):
    import json

    from app.utils.polymarket import get_ai_performance

    _write_alerts_csv(str(tmp_path))
    with open(os.path.join(str(tmp_path), "ai_loop_state.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "global_ai_policy": "shadow",
                "counters": {},
                "last_screen_meta": {
                    "ts": "2026-04-13T12:00:00Z",
                    "verdict": "BET",
                    "short_summary": "Looks fine",
                    "reason_codes": ["liquidity_ok"],
                    "screen_model": "gpt-test",
                    "prompt_version": "1",
                },
            },
            f,
        )

    out = get_ai_performance(str(tmp_path), strategy="all")
    assert out["producer_last_screen_meta"]["verdict"] == "BET"
    assert out["producer_last_screen_meta"]["reason_codes"] == ["liquidity_ok"]
    assert out["ai_loop_display_source"] == "live"


def test_get_ai_performance_ignores_artifact_when_stale(tmp_path):
    import json

    from app.utils.polymarket import get_ai_performance

    _write_alerts_csv(str(tmp_path))
    art = {
        "schema_version": 1,
        "exported_at": "2026-01-01T00:00:00+00:00",
        "freshness": {"alerts_log_csv_mtime": 1.0},
        "producer": {},
        "performance": {
            "has_data": True,
            "accuracy_tiers": [],
            "blocked_rows": [],
            "blocked_rows_full_count": 0,
            "total_screened": 99999,
            "total_blocked": 0,
            "overall_accuracy": None,
            "baseline_loss_rate": None,
            "cf_standard_bet": 100.0,
            "lift_metrics": {},
        },
        "sim": {},
    }
    with open(os.path.join(str(tmp_path), "ai_performance.json"), "w", encoding="utf-8") as f:
        json.dump(art, f)

    out = get_ai_performance(str(tmp_path), strategy="all")
    assert out["data_source"] == "csv"
    assert out["total_screened"] != 99999


def test_get_ai_sim_stats_uses_fresh_artifact(tmp_path):
    import json

    from app.utils.polymarket import get_ai_sim_stats

    _write_alerts_csv(str(tmp_path))
    csv_path = os.path.join(str(tmp_path), "alerts_log.csv")
    csv_m = os.path.getmtime(csv_path)

    art = {
        "schema_version": 1,
        "exported_at": "2026-01-01T00:00:00+00:00",
        "freshness": {"alerts_log_csv_mtime": csv_m},
        "producer": {"global_ai_policy": "shadow"},
        "performance": {},
        "sim": {
            "alerts_total": 1,
            "open_list": [],
            "resolved_list": [
                {
                    "question": "Q sim",
                    "actual_result": "YES",
                    "pnl_usd": 12.5,
                    "link": "https://polymarket.com/market/q-safe",
                    "bet_size_usd": 100.0,
                    "ai_verdict": "BET",
                    "ai_confidence": "High",
                    "ai_red_flags": [],
                    "sport": "crypto",
                    "strategy_id": "safe_fast",
                    "resolved_ts": "2026-03-31T11:00:00+00:00",
                    "ts": "2026-03-31T10:00:00+00:00",
                },
            ],
        },
    }
    with open(os.path.join(str(tmp_path), "ai_performance.json"), "w", encoding="utf-8") as f:
        json.dump(art, f)

    sim = get_ai_sim_stats(str(tmp_path), strategy="all")
    assert sim is not None
    assert sim["data_source"] == "artifact"
    assert sim["alerts_total"] == 1
    assert sim["resolved"] == 1
    assert sim["producer_global_ai_policy"] == "shadow"
    assert sim["ai_loop_display_source"] == "artifact_snapshot"


def test_get_alerts_status_summary_blocked_risk_limit_and_top_buckets(tmp_path):
    """blocked_risk_limit rows aggregate counts and top risk_bucket breakdown."""
    import csv

    from app.utils.polymarket import get_alerts_status_summary

    rows = [
        {"status": "sent", "primary_block_reason": "", "risk_bucket": "ignore"},
        {
            "status": "blocked_risk_limit",
            "primary_block_reason": "MAX_CATEGORY_EXPOSURE_USD",
            "risk_bucket": "sports_short",
        },
        {
            "status": "blocked_risk_limit",
            "primary_block_reason": "MAX_CATEGORY_EXPOSURE_USD",
            "risk_bucket": "sports_short",
        },
        {
            "status": "blocked_risk_limit",
            "primary_block_reason": "MAX_CATEGORY_EXPOSURE_USD",
            "risk_bucket": "crypto",
        },
    ]
    path = os.path.join(str(tmp_path), "alerts_log.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    s = get_alerts_status_summary(str(tmp_path))
    assert s["logged"] == 4
    assert s["sent"] == 1
    assert s["blocked"] == 3
    assert s["blocked_risk_limit"] == 3
    assert s["top_risk_buckets"][0]["bucket"] == "sports_short"
    assert s["top_risk_buckets"][0]["count"] == 2
    assert any(tb["bucket"] == "crypto" and tb["count"] == 1 for tb in s["top_risk_buckets"])


import pytest  # noqa: E402 (import after test functions to keep helper proximity)
