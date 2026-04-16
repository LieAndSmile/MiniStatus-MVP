"""Shared constants for Polymarket dashboard (strategies, sort keys, schema, buckets)."""

# Must stay in sync with polymarket-alerts config.JSON_ARTIFACT_SCHEMA_VERSION for JSON artifacts we fully support.
SUPPORTED_JSON_ARTIFACT_SCHEMA_VERSION = 2

# Required columns for alerts_log.csv schema validation
ALERTS_LOG_REQUIRED = ("question", "pnl_usd", "resolved", "actual_result")
ALERTS_LOG_NEEDS_ONE_OF = ("ts", "resolved_ts")

# v3: strategy filter options (match strategies.yaml; extended for Phase 1–3 probes and strategy rework)
STRATEGY_OPTIONS = (
    "safe",
    "safe_fast",
    "safe_same_day_core",
    "safe_1to2d_core",
    "safe_premium",
    "safe_swing_low_gamma",
    "safe_v2",
    "same_day_probe",
    "hold_3to7d_probe",
    "hold_8to10d_probe",
    "gamma_84_86_probe",
    "gamma_86_92_probe",
    "gamma_92_96_probe",
    "mid_gamma",
    "resolution_sprint",
)

# One-line operator hints (Portfolio Strategy Overview). Keys optional; missing keys show no extra line.
STRATEGY_SHORT_HELP: dict[str, str] = {
    "safe_same_day_core": (
        "Resolves same day as the scan — primary active short-hold cohort; full size multiplier unless YAML says otherwise."
    ),
    "safe_1to2d_core": (
        "Resolves in 1–2 days — isolated from same-day P/L; typically smaller size so the slower cohort does not dominate risk."
    ),
    "safe_fast": "Legacy strategy id in older logs only; new rows use same-day or 1–2d core strategies.",
    "safe_premium": "Separate premium tier; evaluate on its own track before changing sizing.",
}

STRATEGY_LABELS: dict[str, str] = {
    "safe": "Safe (legacy)",
    "safe_fast": "Safe fast (legacy)",
    "safe_same_day_core": "Safe same-day core",
    "safe_1to2d_core": "Safe 1–2d core",
    "safe_premium": "Safe premium",
    "safe_swing_low_gamma": "Safe swing / low γ",
    "safe_v2": "Safe v2",
    "same_day_probe": "Same-day probe",
    "hold_3to7d_probe": "Hold 3–7d probe",
    "hold_8to10d_probe": "Hold 8–10d probe",
    "gamma_84_86_probe": "Gamma 84–86 probe",
    "gamma_86_92_probe": "Gamma 86–92 probe",
    "gamma_92_96_probe": "Gamma 92–96 probe",
    "mid_gamma": "Mid gamma",
    "resolution_sprint": "Resolution sprint",
}

STRATEGY_MODE: dict[str, str] = {
    "safe": "disabled",
    "safe_fast": "disabled",
    "safe_same_day_core": "active",
    "safe_1to2d_core": "active",
    "safe_premium": "active",
    "safe_swing_low_gamma": "shadow",
    "safe_v2": "shadow",
    "same_day_probe": "shadow",
    "hold_3to7d_probe": "shadow",
    "hold_8to10d_probe": "shadow",
    "gamma_84_86_probe": "shadow",
    "gamma_86_92_probe": "shadow",
    "gamma_92_96_probe": "shadow",
    "mid_gamma": "shadow",
    "resolution_sprint": "shadow",
}


BLOCK_REASON_LABELS: dict[str, str] = {
    "MAX_TOTAL_RISK_USD": "Portfolio cap reached",
    "MAX_OPEN_POSITIONS": "Max positions open",
    "MAX_CATEGORY_EXPOSURE_USD": "Per-bucket exposure cap (risk_bucket)",
    "MAX_STRATEGY_EXPOSURE_USD": "Strategy limit reached",
    "blocked_inactive_strategy": "Strategy inactive",
}

# Empty stats structure for error/fallback responses
_STATS_EMPTY = {
    "alerts_total": 0,
    "resolved": 0,
    "wins": 0,
    "losses": 0,
    "total_pnl": 0.0,
    "total_pnl_display": "$0.00",
    "resolved_list": [],
    "chart_data": [],
    "max_drawdown": 0,
    "max_drawdown_display": "$0.00",
    "worst_period": "",
}

SORT_OPTIONS = (
    "pnl_asc",      # P/L lowest first (biggest losses first)
    "pnl_desc",     # P/L highest first (biggest wins first)
    "date_desc",    # Newest first
    "date_asc",     # Oldest first
    "question_asc", # Question A–Z
    "question_desc",# Question Z–A
    "result_yes",   # YES first
    "result_no",    # NO first
)

POSITIONS_SORT_OPTIONS = (
    "cost_desc", "cost_asc", "pnl_desc", "pnl_asc",
    "gamma_desc", "gamma_asc", "edge_desc", "edge_asc",
    "expiry_asc", "expiry_desc",
    "question_asc", "question_desc", "date_desc", "date_asc",
    "interesting_first",
)

INTERESTING_POSITIONS_FILENAME = "interesting_positions.json"

POSITIONS_EXPIRY_FILTERS = ("all", "next_6h", "next_12h", "next_24h", "next_48h", "next_3d", "next_7d", "next_30d")

# Tolerances for "near risky" (plan: edge 0.25 pp, gamma 0.02, expiry 12h)
NEAR_RISKY_EDGE_TOL = 0.0025   # 0.25 percentage points
NEAR_RISKY_GAMMA_TOL = 0.02
NEAR_RISKY_EXPIRY_TOL_HOURS = 12.0

# Keywords to categorize markets for loss breakdown (case-insensitive)
_LOSS_CATEGORIES = {
    "politics": [
        "trump", "biden", "election", "congress", "senate", "president", "governor",
        "vote", "iran", "israel", "ukraine", "russia", "putin", "zelensky",
        "democrat", "republican", "primary", "nominee", "cabinet", "impeach",
    ],
    "sports": [
        "fc", " vs ", "o/u", "over", "under", "nfl", "nba", "mlb", "nhl",
        "soccer", "football", "basketball", "baseball", "hockey", "spread",
        "mariners", "jets", "wolves", "united", "wanderers", "wolverhampton",
    ],
    "crypto": [
        "bitcoin", "btc", "eth", "ethereum", "solana", "sol ", "crypto",
        "cryptocurrency", "defi", "nft",
    ],
    "entertainment": [
        "oscar", "grammy", "emmy", "award", "movie", "film", "album",
    ],
}

DEBUG_SORT_OPTIONS = (
    "date_desc",     # Newest first
    "date_asc",      # Oldest first
    "edge_desc",     # Highest edge first
    "edge_asc",      # Lowest edge first
    "question_asc", # Question A–Z
    "question_desc",# Question Z–A
    "status",       # ALERT first, then EFFECTIVE_OUT
    "hrs_asc",      # Hrs left soonest first
    "hrs_desc",     # Hrs left latest first
)

# Loop/Dev Hrs left filter presets (max hours): same idea as Open Positions expiry filter
LOOP_HOURS_MAX_PRESETS = (6, 12, 24, 48)  # ≤6h, ≤12h, ≤24h, ≤48h

# Proxy bet size used for blocked_ai_screen counterfactual P/L (real size is unknown).
_CF_STANDARD_BET = 100.0
