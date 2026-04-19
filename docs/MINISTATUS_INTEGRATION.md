## MiniStatus ↔ Polymarket Alerts – Consumer Integration Guide

This document describes **how MiniStatus-MVP consumes data produced by the separate `polymarket-alerts` repo**.  
It is written purely from the **MiniStatus (consumer) perspective**: what we read, which pages depend on it, and how to re‑test MiniStatus when the producer changes.

> **Producer contract source of truth**  
> The canonical producer-side schema and contract live in  
> `polymarket-alerts/docs/INTEGRATION_CONTRACT.md`.  
> That document defines the full field-level contract for each artifact.  
> This file only documents how MiniStatus uses those artifacts.

> **Short “what’s done / what’s left” notes:** canonical `polymarket-alerts/docs/AI_MINISTATUS_TRACKER.md`

---

### 1. What MiniStatus Reads from `polymarket-alerts`

All Polymarket data is read from a single directory configured via:

- **Env var**: `POLYMARKET_DATA_PATH`  
  Example: `/home/ubuntu/polymarket-alerts`

MiniStatus consumes the following artifacts under that directory:

- **`alerts_log.csv`**
  - Used for:
    - Portfolio tab (`/polymarket/portfolio`): resolved alerts list, P/L cards, charts.
    - Loss Lab tab (`/polymarket/loss-lab`): loss breakdowns, buckets, monthly trend.
    - Risky tab (`/polymarket/risky`): historical performance section.
    - Per-run trend script `log_run_stats.py` (which writes `run_stats.csv`).
  - MiniStatus expects:
    - A v3-style alerts log conforming to the producer contract (includes per-alert P/L, result, timestamps, optional strategy and diagnostics).

- **`open_positions.csv`**
  - Used for:
    - Open Positions tab (`/polymarket/positions`): all current positions and filters.
    - Risky tab (`/polymarket/risky`): live risky and near‑risky positions and exposure.
  - MiniStatus expects:
    - One row per open position with identity (market/question), cost/P&L, optional strategy, and optional event time for expiry/countdown.

- **`debug_candidates*.csv`** (typically `debug_candidates.csv`)
  - Used for:
    - Loop / Dev tab (`/polymarket/loop`).
    - Debug export endpoint (`/polymarket/export-debug`).
  - MiniStatus expects:
    - One row per debug candidate with timestamp, question, edge/gamma/hrs‑left metrics, and optional status/strategy.

- **`run_stats.csv`**
  - Produced by `log_run_stats.py` (usually copied into `polymarket-alerts`).
  - Used for:
    - Portfolio tab “Per‑Run Stats Trend” charts (resolved count and cumulative P/L).

- **`analytics.json`**
  - Produced by `analytics_export.py`.
  - Used for:
    - Analytics tab (`/polymarket/analytics`): Edge Quality, Timing, Strategy Cohort, Drift/Exit Study, Insights.

- **`lifecycle.json`**
  - Produced by `evaluate_strategy_lifecycle.py`.
  - Used for:
    - Lifecycle tab (`/polymarket/lifecycle`): strategy verdicts, progress, thresholds.

- **`ai_performance.json`** (optional; producer precomputed snapshot)
  - Produced by `polymarket-alerts/analytics/ai_performance_export.py` (often via `scripts/export_analytics_lifecycle.sh`).
  - Used for:
    - **AI Performance** (`/polymarket/ai-performance`) when the file is present, `schema_version` is supported, and **`alerts_log.csv` was not modified after export** (its mtime is **not greater than** `freshness.alerts_log_csv_mtime`; a newer file triggers a live CSV rescan).
    - **AI Simulation** (`/polymarket/ai-simulation`) under the same freshness rule; strategy filter is applied to the embedded sim lists. Live paper bankroll still comes from `ai_sim_bankroll.json`.
  - **All-strategies summary**: the artifact’s `performance` block reflects **all** strategies; per-strategy AI Performance still uses `alerts_log.csv` only.
  - **Phase 3:** when **`ai_loop_state.json`** exists on `POLYMARKET_DATA_PATH`, MiniStatus **prefers it** for producer counters / policy / timestamps shown in the AI tabs (export snapshot is fallback only).
  - **Phase 4:** producer persists **`last_screen_meta`** after each successful LLM screen (summaries, **`reason_codes`**, model id, **`prompt_version`**); MiniStatus shows it inside **AI loop diagnostics**.

- **`polymarket_alerts.log`**
  - Produced by the polymarket-alerts main loop.
  - Used for:
    - “last run” timestamps on Portfolio and Loop / Dev tabs.
    - Health JSON endpoints (`/polymarket/health`, `/polymarket/freshness`) – `last_loop_run`.

- **`interesting_positions.json`**
  - Owned and written by MiniStatus:
    - Stores the set of “interesting” `market_id`s marked from the Open Positions UI.
  - Used for:
    - Open Positions and Risky tabs when showing/ filtering “interesting” positions.

- **`mirror_portfolio.json`** (optional, producer-generated)
  - Produced by `polymarket-alerts` `analytics/mirror_portfolio_export.py` (or MiniStatus “Refresh from API” on the Mirror Portfolio tab).
  - Used for:
    - **Mirror Portfolio** tab (`/polymarket/mirror-portfolio`): public-wallet trade mirror, ledger, P/L, anomalies.

- **`mirror_watch_config.json`** (optional; **written by MiniStatus**)
  - Lists watched `0x` addresses (max 20), labels, `telegram_enabled`, and **`poll_group`** (`standard` | `fast`) per wallet for the producer job `jobs/mirror_watch.py`.
  - **Split cadence:** On the polymarket-alerts host, run two timers (e.g. 5 min + 1 min) with `python jobs/mirror_watch.py --once --poll-group standard` vs `--poll-group fast`; disable the single “all wallets” timer when using split mode. See polymarket-alerts `systemd/README.md`.
  - Used for:
    - **Mirror alerts** tab (`/polymarket/mirror-alerts`) only (edit UI). The producer reads this file on the same `POLYMARKET_DATA_PATH` host.

---

### 2. Page / Route Dependency Map

- **`/polymarket/portfolio` (Portfolio)**
  - **Artifacts**: `alerts_log.csv`, `run_stats.csv`, `polymarket_alerts.log`
  - **Features depending on them**:
    - Summary metrics (net P/L, wins/losses, counts).
    - Resolved alerts table and filters (time window, category, strategy, sort).
    - Cumulative P/L + drawdown charts.
    - Per‑run trend charts (if `run_stats.csv` exists).
    - “polymarket-alerts last run” timestamp from log.

- **`/polymarket/positions` (Open Positions)**
  - **Artifacts**: `open_positions.csv`, `interesting_positions.json`
  - **Features**:
    - Positions list, KPIs (total cost, unrealized P/L).
    - Filters: time window, category, expiry window, strategy, “interesting only”.
    - “Mark as interesting” toggles (via `interesting_positions.json`).

- **`/polymarket/risky` (Risky)**
  - **Artifacts**: `open_positions.csv`, `alerts_log.csv`
  - **Features**:
    - Risky positions table and KPIs, Risky exposure by category.
    - Near‑risky positions table.
    - Historical Risky performance (resolved alerts that would have met thresholds).

- **`/polymarket/loss-lab` (Loss Lab)**
  - **Artifacts**: `alerts_log.csv`
  - **Features**:
    - Loss breakdown by derived category (e.g. politics/sports/crypto).
    - Bucket breakdowns (edge, gamma, hold/time‑to‑resolution).
    - Monthly net P/L trend per category.

- **`/polymarket/analytics` (Analytics)**
  - **Artifacts**: `analytics.json`
  - **Features**:
    - Strategy Insights block.
    - Edge Quality, Timing, Strategy Cohort, Drift/Exit Study tables.
    - Strategy filter (including any new strategies present in analytics).

- **`/polymarket/lifecycle` (Lifecycle)**
  - **Artifacts**: `lifecycle.json`
  - **Features**:
    - Strategy verdicts and progress against thresholds.
    - Strategy filter and lifecycle event history (when present).

- **`/polymarket/ai-performance` (AI Performance)**
  - **Artifacts**: `ai_performance.json` (when fresh), else `alerts_log.csv`; optional `ai_loop_state.json` fields surfaced when present inside the artifact’s `producer` section.
  - **Features**:
    - Screener accuracy by tier, blocked-row review, lift / false-block metrics; UI shows whether data came from the artifact or a CSV scan.

- **`/polymarket/ai-simulation` (AI Simulation)**
  - **Artifacts**: `ai_performance.json` (when fresh) or `alerts_log.csv` for sim rows; `ai_sim_bankroll.json` for bankroll widget.
  - **Features**:
    - Resolved/open sim bets, charts, filters; data source called out in-page when the artifact is used.

- **`/polymarket/loop` (Loop / Dev)**
  - **Artifacts**: `debug_candidates*.csv`, `polymarket_alerts.log`
  - **Features**:
    - Loop summary table with filters (status, hrs left, date, strategy).
    - Hrs‑left and countdown computations.
    - “Last run” indicator based on LOOP SUMMARY log lines.

- **`/polymarket/mirror-portfolio` (Mirror Portfolio)**
  - **Artifacts**: `mirror_portfolio.json` (optional)
  - **Features**:
    - Summary, ledger (truncated), open positions, resolution events, anomalies; POST refresh runs producer export script on the server.

- **`/polymarket/mirror-alerts` (Mirror alerts)**
  - **Artifacts**: `mirror_watch_config.json` (read/write; optional until first save)
  - **Features**:
    - Add/remove watched wallets; toggle Telegram per wallet; does **not** send Telegram itself (producer `jobs/mirror_watch.py` + timer).

- **JSON health endpoints**
  - **`/polymarket/health`**, **`/polymarket/freshness`**
  - **Artifacts**: All of the above (for ages + quick schema check on `alerts_log.csv`).

---

### 3. Fallback Behavior (Missing / Stale / Invalid Data)

MiniStatus is designed to **fail soft** on integration issues and surface clear signals instead of crashing:

- **`POLYMARKET_DATA_PATH` missing / invalid**
  - All Polymarket tabs render a “not configured” card.
  - `/polymarket/health` and `/polymarket/freshness` respond with `configured: false`.

- **`alerts_log.csv`**
  - **Missing**:
    - Portfolio, Loss Lab, Risky historical behave as if there are no resolved alerts.
    - UI copy states that data is read from `alerts_log.csv`.
  - **Schema mismatch** (e.g. missing required columns):
    - Portfolio shows a dedicated **CSV schema mismatch** banner and no stats/table.
    - `alerts_schema_ok` is `false` in `/polymarket/health`.
  - **Row-level issues** (e.g. bad numbers or timestamps):
    - Problematic values are defaulted or excluded; aggregations may be off but pages continue to render.

- **`open_positions.csv`**
  - **Missing**:
    - Open Positions and Risky tabs show “No positions” / “No risky positions” states.
  - **Partial / malformed rows**:
    - Rows missing key fields may be filtered out of some views or show “—” for derived values; tabs still render.

- **`debug_candidates*.csv`**
  - **Not found**:
    - Loop / Dev tab shows an empty-state message explaining that the debug candidates CSV is missing.

- **`run_stats.csv`**
  - **Missing or unreadable**:
    - Portfolio simply hides the Per‑Run Stats Trend charts while leaving the rest intact.

- **`analytics.json` / `lifecycle.json`**
  - **Missing**:
    - Their respective tabs render empty or explanatory states; no 500s.
  - **Wrong top-level types**:
    - Non-dict values are normalized to `{}` before templates; sections become empty rather than crashing.

- **`ai_performance.json`**
  - **Missing or stale** (CSV newer than embedded `freshness.alerts_log_csv_mtime`, or unreadable schema):
    - AI Performance and AI Simulation fall back to scanning `alerts_log.csv` (same metrics semantics where applicable).
  - **Present and fresh**:
    - Pages may show “precomputed export” as the data source; producer counters / policy timestamps appear when the export included them.

- **`polymarket_alerts.log`**
  - **Missing / no LOOP SUMMARY lines**:
    - “Last run” labels are omitted or show “log not found”; the rest of each tab works normally.

- **`mirror_portfolio.json`**
  - **Missing**:
    - Mirror Portfolio tab shows an empty state and CLI hint; no 500s.

- **`mirror_watch_config.json`**
  - **Missing**:
    - Mirror alerts tab shows an empty watch list; producer job may still use `MIRROR_WATCH_WALLET` from `.env` until the JSON file exists.

---

### 4. MiniStatus-Specific Retest Checklist

When **polymarket-alerts** changes any integration‑relevant artifact or contract, re‑test MiniStatus as follows:

1. **Health / freshness probes**
   - Call `GET /polymarket/health`:
     - `configured == true`
     - `alerts_schema_ok == true`
     - `alerts_schema_error == null`
   - Call `GET /polymarket/freshness`:
     - `freshness.alerts_log_age`, `open_positions_age`, `debug_candidates_age`, `ai_performance_age`, etc. are **recent enough** for your SLO.

2. **Portfolio tab**
   - Loads without warnings except expected empty‑data states.
   - Summary cards (Net P/L, wins/losses, total alerts, resolved) look plausible.
   - Resolved alerts table is populated; filters (time window, category, strategy, sort) behave correctly.
   - P/L and drawdown charts render.
   - Per‑Run Stats Trend charts appear when `run_stats.csv` exists.

3. **Open Positions and Risky tabs**
   - Open Positions list is populated; totals and per‑row values make sense.
   - Time window, category, expiry, and strategy filters all work.
   - “Interesting” toggles persist across reloads.
   - Risky and Near‑Risky sections populate with plausible positions.
   - Risky historical performance section renders without 500s and numbers trend as expected.

4. **Loss Lab, Analytics, Lifecycle**
   - Loss Lab:
     - Category cards show counts and P/L.
     - Edge/gamma/hold/time‑to‑resolution buckets and monthly trend appear and react to filters.
   - Analytics:
     - Edge Quality, Timing, Strategy Cohort, Drift/Exit Study sections display data.
     - Strategy filter works for both static and new strategies from analytics.
   - Lifecycle:
     - Verdicts table renders; strategy filter and progress indicators behave correctly.

5. **Loop / Dev**
   - Loop table loads with recent debug candidates.

6. **Mirror Portfolio / Mirror alerts**
   - After generating `mirror_portfolio.json` on the producer host, Mirror Portfolio shows data; refresh POST succeeds (CSRF).
   - Mirror alerts: add a test wallet, toggle Telegram, remove; confirm `mirror_watch_config.json` updates on disk under `POLYMARKET_DATA_PATH`.
   - Status and hrs‑left filters, date filters, and all sort modes behave as expected.
   - Export Debug CSV downloads and opens with sensible content.

If any of the above fail **without MiniStatus code changes**, investigate for producer–consumer drift in `polymarket-alerts` against `polymarket-alerts/docs/INTEGRATION_CONTRACT.md`.

