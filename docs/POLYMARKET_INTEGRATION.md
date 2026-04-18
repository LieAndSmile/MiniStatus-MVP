## Polymarket Integration – Consumer-Side Contract (MiniStatus-MVP)

> **Note:** This file is an implementation-level reference for MiniStatus as a **consumer**.  
> The **canonical producer-side contract** (field-level schema, evolution rules, etc.) lives in  
> `polymarket-alerts/docs/INTEGRATION_CONTRACT.md`.  
> When in doubt, treat that producer document as source of truth and this file as a consumer-oriented companion.

This document describes how **MiniStatus-MVP** consumes data produced by the separate **polymarket-alerts** repo. It focuses on integration points, expected schemas as they are currently used, and failure modes – not product feature design.

**Schema sync:** When `alerts_log.csv` columns change in polymarket-alerts, follow the **Schema change checklist** in `polymarket-alerts/docs/INTEGRATION_CONTRACT.md`. Copy `polymarket-alerts/docs/alerts_log_header.json` to **`tests/fixtures/alerts_log_header.json`** here and run `pytest tests/test_polymarket_alerts_schema_fixture.py`.

**CI minimal deps:** After changing **`requirements.txt`**, regenerate **`requirements-ci-minimal.txt`** with `python scripts/sync_requirements_ci_minimal.py` so the **`test-ci-minimal`** workflow stays in sync.

**Operational context:** Expected update cadences for CSV/JSON files live in **`polymarket-alerts/docs/RUNBOOK.md`** (“Data pipeline”). The Polymarket nav includes a **Data freshness** strip (artifact ages + link to `/polymarket/freshness` JSON).

**MiniStatus restart:** After deploying code or template changes, restart the WSGI service so the dashboard serves the new bits: `./scripts/restart.sh` or `sudo systemctl restart ministatus` (see **Service Management** in the repo **`README.md`**).

---

### 1. Data Location and Configuration

- **Environment variable**: `POLYMARKET_DATA_PATH`
  - **Meaning**: Absolute path to the polymarket-alerts data directory on the same host.
  - **Examples**: `/home/ubuntu/polymarket-alerts`
  - **Usage in code**:
    - `app.utils.polymarket.is_polymarket_configured()`
    - `app.routes.polymarket._get_data_path()`
    - `app.utils.polymarket_health._get_data_path()`
  - **Behavior when missing/invalid**:
    - All Polymarket tabs render a “not configured” message instead of failing.
    - `/polymarket/health` and `/polymarket/freshness` return `configured: false`.

All consumer paths below are **relative to `POLYMARKET_DATA_PATH`** unless noted otherwise.

---

### 2. External Artifacts and Schemas

#### 2.1 `alerts_log.csv`

- **Path**: `<POLYMARKET_DATA_PATH>/alerts_log.csv`
- **Producer note:** polymarket-alerts `jobs/resolution_tracker.py` writes resolution fields on the row identified by **`alert_id`** (legacy rows: same `token_id` + `ts`). If you see inconsistent resolved counts vs Polymarket’s actual outcomes, ensure polymarket-alerts is current and run the upstream repair script if needed (`scripts/repair_duplicate_token_resolutions.py`; see polymarket-alerts `docs/RUNBOOK.md`).
- **Consumed by**:
  - `app.utils.polymarket.get_polymarket_stats()`
  - `app.utils.polymarket.validate_alerts_log_schema()`
  - `app.utils.polymarket.get_loss_breakdown()`
  - `app.utils.polymarket.get_loss_breakdown_buckets()`
  - `app.utils.polymarket.get_loss_trend_by_category()`
  - `app.utils.polymarket.get_risky_historical_performance()`
  - `app.utils.polymarket_health.get_polymarket_freshness()` (file age)
  - Scripts copied to polymarket-alerts:
    - `scripts/log_run_stats.py`
    - `scripts/analyze_losses_by_category.py`
- **Primary routes / pages**:
  - `/polymarket/portfolio` (Portfolio tab)
  - `/polymarket/loss-lab` (Loss Lab tab)
  - `/polymarket/risky` (historical performance section)
  - Indirectly: Portfolio charts, Loss Lab buckets/trend

**Expected schema**

MiniStatus expects the **current producer header** maintained by polymarket-alerts (`alerts_log_writer.ALERTS_HEADER`; schema **v7** adds **`event_key`** between `sport` and `market_type`). The canonical ordered list is **`polymarket-alerts/docs/alerts_log_header.json`** — copy it to **`tests/fixtures/alerts_log_header.json`** when the producer changes columns.

- Required columns (case-insensitive, validated by `validate_alerts_log_schema`):
  - `question`
  - `pnl_usd`
  - `resolved`
  - `actual_result`
  - **at least one** of `ts` or `resolved_ts`
- **Full column order** matches **`polymarket-alerts/docs/alerts_log_header.json`** ( sizing fields, `risk_bucket`, `sport`, **`event_key`**, `market_type`, AI columns, etc.). If this paragraph and the repo JSON disagree, trust the JSON and update **`tests/fixtures/alerts_log_header.json`**.

**Navigation / scroll**

- Polymarket section links (sidebar and tab bar) save **`sessionStorage.polymarket_scroll`** so the main window restores vertical scroll position when switching tabs or strategies (`app/templates/base.html`, `polymarket_nav.html`). Sort dropdowns must **not** use `data-polymarket-nav` (that attribute is reserved for strategy links).

**How it is used**

- Portfolio (`get_polymarket_stats`):
  - Filters resolved rows (`resolved` true or `actual_result` in {YES, NO}).
  - Parses `pnl_usd` as float.
  - Derives:
    - counts: alerts_total, resolved, wins, losses
    - cumulative P/L series (`chart_data`)
    - max drawdown and worst period
    - per-row rationale from `gamma`, `best_ask`, `effective`, `fill_pct`, `edge`, `spread`
    - optional category classification from `question`
  - Supports global filters:
    - `days` / `from_date` based on `resolved_ts`/`ts`
    - `category` via `_categorize_question`
    - `strategy_id` via `strategy` parameter
- Loss Lab (`get_loss_breakdown`, `get_loss_breakdown_buckets`, `get_loss_trend_by_category`):
  - Only **losing resolved** rows (`pnl_usd < 0` and resolved).
  - Uses `question` for derived categories and examples.
  - Uses timestamps for time-window filters and monthly aggregation.
- Risky historical (`get_risky_historical_performance`):
  - Uses `edge`, `gamma`, `ts`, `resolved_ts`, `pnl_usd`, `cost_usd` or `fill_usdc`.
  - Applies thresholds (edge_min, gamma_max, expiry_hours_max) on resolved alerts.
  - Aggregates ROI, averages (edge, gamma, hold duration), and per-category stats.
- Health and tooling:
  - `validate_alerts_log_schema` is called before most consumers.
  - `log_run_stats.py` and `analyze_losses_by_category.py` use the same resolved / P&L logic.

**Missing / stale / invalid handling**

- If `alerts_log.csv` **does not exist**:
  - `get_polymarket_stats` / Loss Lab / Risky historical return empty/default structures.
  - UI shows “No resolved alerts yet. Data is read from alerts_log.csv.”
- If schema validation fails (`validate_alerts_log_schema`):
  - Portfolio returns `_STATS_EMPTY` with an `error` field prefixed with `CSV schema mismatch`.
  - Portfolio template shows a prominent red **CSV schema mismatch** banner with details and does **not** render stats / tables.
  - Loss Lab / other views are conservative and generally fall back to empty results when underlying reads fail.
  - When required columns are missing and the file has **≤3** header columns (non-canonical header: wrong `POLYMARKET_DATA_PATH`, corrupt file, or stray test CSV), the error text includes a short hint to run **`polymarket-alerts`** `scripts/validate_alerts_log.py --csv "$POLYMARKET_DATA_PATH/alerts_log.csv" --repair`, which saves the bad file as **`alerts_log.csv.bak.noncanonical`** and writes a canonical header-only log upstream (`validate_alerts_log.py` since **v6.4.1**).
- If specific fields fail to parse:
  - Numeric parsing functions (`_parse_float`, etc.) default to 0.0 and keep the row, which can influence aggregates but not crash rendering.

**Producer / consumer drift risks**

- Renaming or dropping any of the **required columns** (`question`, `pnl_usd`, `resolved`, `actual_result`, `ts`/`resolved_ts`) breaks:
  - Portfolio stats and lists
  - Loss Lab and Risky historical (and derived charts)
  - `log_run_stats.py` and `analyze_losses_by_category.py`
- Changing types or semantics:
  - `resolved` must remain a boolean-ish field (true/1/yes).
  - `pnl_usd` must stay numeric (stringified floats).
  - `ts` / `resolved_ts` must remain parseable timestamps in one of the expected formats.
- Column order: producer must keep the same order as `ALERTS_HEADER` to interoperate with existing writer/validators.

**What to test after producer changes**

- Run `polymarket-alerts` own tools:
  - `python validate_alerts_log.py --csv alerts_log.csv`
  - `python log_run_stats.py --dry-run`
  - `python analyze_losses_by_category.py --csv alerts_log.csv`
- In MiniStatus:
  - Portfolio tab (resolved list, charts, win/loss counts) loads without errors.
  - Loss Lab tab (category cards, bucket breakdowns, monthly trend) renders with non-empty data.
  - Risky tab → “Risky historical performance” section shows sane numbers (no 500s / template errors).
  - `/polymarket/health` reports `alerts_schema_ok: true`.

---

#### 2.2 `open_positions.csv`

- **Path**: `<POLYMARKET_DATA_PATH>/open_positions.csv`
- **Consumed by**:
  - `app.utils.polymarket.get_open_positions()`
  - `app.utils.polymarket.get_risky_positions()`
  - `app.utils.polymarket.get_near_risky_positions()`
  - `app.utils.polymarket.get_exposure_summary()`
  - `app.utils.polymarket_health.get_polymarket_freshness()` (file age)
- **Primary routes / pages**:
  - `/polymarket/positions` (Open Positions tab)
  - `/polymarket/risky` (Risky and Near Risky tables + KPIs)

**Key columns expected by consumer**

MiniStatus does not validate a fixed schema here but expects the following fields for full functionality:

- Identity:
  - `market_id` (string)
  - `question` (string)
  - `side` (YES/NO)
  - `link` (URL; used only if starts with `http`)
- Numbers:
  - `shares`
  - `avg_price`
  - `cost_usd`
  - `current_mid`
  - `unrealized_pnl`
  - `gamma`
  - `edge`
- Timestamps:
  - `alert_ts` (ISO string; used for filters and display)
  - `event_time` (ISO string; used for expiry and countdown)
- Strategy:
  - `strategy_id` (for strategy dropdown filter)

**How it is used**

- `get_open_positions`:
  - Filters by:
    - time window (`days` / `from_date` using `alert_ts`)
    - category derived from `question`
    - expiry (`expiry_filter` / `hours_max` using `event_time`)
    - `strategy_id`
  - Derives:
    - `alert_ts_display`, `alert_date_param`
    - `edge_pct`
    - `resolution_time_display`, `hours_remaining`, `hours_remaining_display`
    - `countdown`
    - compact cost/unrealized displays
- `get_risky_positions` / `get_near_risky_positions`:
  - Reuse `get_open_positions` output and apply additional thresholds; rely on:
    - `edge` (float)
    - `gamma` (float)
    - `hours_remaining`
- `get_exposure_summary`:
  - Groups positions by derived category and uses `cost_usd`, `unrealized_pnl`.

**Missing / stale / invalid handling**

- If `open_positions.csv` is **missing**:
  - `get_open_positions` returns an empty list; Open Positions and Risky tables show “No open positions” / “No risky positions”.
  - Risky KPI cards and exposure table adapt to the empty list without raising errors.
- If specific fields are missing or malformed:
  - Numeric fields use `_parse_float` with defaults (often 0.0).
  - Non-numeric or missing timestamps will disable some filters (e.g. expiry windows) for that row, but not crash the view.

**Producer / consumer drift risks**

- Removing `alert_ts` or `event_time` breaks time-window and expiry filters and countdowns.
- Removing or reinterpreting `gamma` / `edge` distorts or breaks Risky / Near Risky classification.
- Changing `market_id` semantics without updating `interesting_positions.json` logic can make “interesting” toggles inconsistent (see below).

**What to test after producer changes**

- In MiniStatus:
  - `/polymarket/positions`:
    - Filters: time window, category, expiry ranges, sort options all behave sensibly.
    - Cost and unrealized P/L totals and per-row values look correct.
  - `/polymarket/risky`:
    - Risky and Near Risky tables render with expected rows.
    - KPI cards (cost, unrealized P/L, historical performance) render without 500s.
    - Changing presets and strategy filters recomputes results without errors.

---

#### 2.3 `debug_candidates*.csv`

- **Path resolution** (Loop / Dev tab, `get_debug_candidates`):
  - Prefer:
    - `<POLYMARKET_DATA_PATH>/<POLYMARKET_DEBUG_CSV>` (default: `debug_candidates.csv`)
    - Fallback: `<POLYMARKET_DATA_PATH>/debug_candidates_v60.csv`
    - Fallback: first match of `<POLYMARKET_DATA_PATH>/debug_candidates*.csv`
- **Consumed by**:
  - `app.utils.polymarket.get_debug_candidates()`
  - `app.utils.polymarket_health.get_polymarket_freshness()` (age of `debug_candidates.csv`)
- **Primary routes / pages**:
  - `/polymarket/loop` (Loop / Dev tab)
  - `/polymarket/export-debug` (full data CSV export)

**Key columns expected by consumer**

From `get_debug_candidates`:

- Identity / description:
  - `ts` (timestamp string)
  - `question`
  - `link` (may be missing; consumer constructs a Polymarket search URL fallback)
- Numbers:
  - `gamma`
  - `best_ask`
  - `spread`
  - `effective`
  - `fill_pct`
  - `edge`
  - `days`
  - `hrs_left` (optional; recomputed from `event_time` when present)
- Timestamps:
  - `event_time` (optional; used for recomputing Hrs left and countdown)
- Strategy / status:
  - `strategy_id`
  - `status` (expected values: `ALERT`, `EFFECTIVE_OUT`, others)

**How it is used**

- `get_debug_candidates`:
  - Filters by:
    - `strategy_id`
    - `status` (optional “ALERT only”)
    - `from_date` (via parsed `ts`)
    - `hours_max` (via recomputed `hrs_left_float`)
  - Derives:
    - `ts_dt`, `ts_display`, `ts_date_param`
    - `resolution_display` (from `event_time`)
    - `hrs_left_display` and `hrs_left_float`
    - `countdown` (via `_format_countdown`)
- `/polymarket/loop`:
  - Displays all above fields in the Loop / Dev table.
  - Sorts by date, edge, question, status, or hours left using the derived values.
  - Uses `ts_date_param` links to apply date filters.

**Missing / stale / invalid handling**

- If no debug candidates CSV can be found:
  - `get_debug_candidates` returns `None`.
  - Loop / Dev template shows an empty-state message (“No debug candidates data.”).
- If rows have bad timestamps or numeric fields:
  - Parsing is guarded; invalid values become `None`/0 and are excluded from some filters but do not crash rendering.

**Producer / consumer drift risks**

- Removing `ts` or changing its format beyond what `_parse_date` can handle breaks date filters and sorting.
- Removing `event_time` removes the ability to recompute Hrs left; consumer falls back to `hrs_left` if present, otherwise shows `—`.
- Renaming `status` or dropping it breaks the “ALERT only” filter and status-based sorting.

**What to test after producer changes**

- In MiniStatus `/polymarket/loop`:
  - Table loads without errors, with recent candidates.
  - Status filter (All vs ALERT only) and Hrs left filters (All, ≤6h, ≤12h, ≤24h, etc.) behave correctly.
  - Sorting by Time, Edge, Question, Status, Hrs left produces sensible orderings.
  - Export Debug (`/polymarket/export-debug`) downloads a CSV with expected contents.

---

#### 2.4 `run_stats.csv`

- **Path**: `<POLYMARKET_DATA_PATH>/run_stats.csv`
- **Produced by**: `log_run_stats.py` script (copied from MiniStatus into polymarket-alerts).
- **Consumed by**:
  - `app.utils.polymarket.get_run_stats_log()`
- **Primary routes / pages**:
  - `/polymarket/portfolio` → “Per-Run Stats Trend” section (charts).

**Expected schema**

- Header (from `log_run_stats.py`):
  - `ts`
  - `resolved`
  - `wins`
  - `losses`
  - `total_pnl`
  - `alerts_total`

**Missing / stale / invalid handling**

- If `run_stats.csv` is missing or unreadable:
  - `get_run_stats_log` returns an empty list.
  - Portfolio template hides the Per-Run Stats Trend section.
- Invalid numeric fields are parsed via a safe helper; bad values are treated as 0.

**Producer / consumer drift risks**

- Renaming columns or altering their semantics will make charts misleading but should not 500 because the consumer is defensive.

**What to test after producer changes**

- Generate a few runs via `log_run_stats.py`.
- Confirm Portfolio tab shows both resolved-count and P/L trend charts, with labels and values that match expectations.

---

#### 2.5 `analytics.json`

- **Path**: `<POLYMARKET_DATA_PATH>/analytics.json`
- **Produced by**: `analytics_export.py` in polymarket-alerts.
- **Consumed by**:
  - `app.utils.polymarket.get_analytics_json()`
  - `app.utils.polymarket.get_analytics_file_age()`
- **Primary routes / pages**:
  - `/polymarket/analytics`
  - Strategy dropdowns and Insights / Edge Quality / Timing / Strategy Cohort / Drift sections.

**Expected structure (high level)**

- A JSON object; consumer expects keys (when present) to be **dicts**:
  - `strategy_cohort`
  - `edge_quality`
  - `timing`
  - `exit_study`
  - `insights`
  - `totals` (used in templates but guarded)
- Strategy list for dropdown is derived from:
  - Static `STRATEGY_OPTIONS` unioned with `analytics["strategy_cohort"].keys()` when that value is a dict.

**Missing / stale / invalid handling**

- If `analytics.json` is missing:
  - `get_analytics_json` returns `None`.
  - Analytics tab renders an appropriate empty state.
- If `analytics.json` fields are not dicts (e.g. list, null):
  - Analytics route normalizes them to `{}` before hitting the template.
  - `get_strategy_options_for_nav` treats non-dict `strategy_cohort` as empty.

**Producer / consumer drift risks**

- Changing top-level keys to different types (e.g. array instead of object) is tolerated but may hide certain sections.
- Removing required subfields inside those dicts affects what the UI can display (e.g. missing ROI fields), but templates are mostly defensive and use `"—"` or empty states instead of crashing.

**What to test after producer changes**

- Run `analytics_export.py` to refresh `analytics.json`.
- In MiniStatus `/polymarket/analytics`:
  - Edge Quality, Timing, Strategy Cohort, Exit Study/Drift sections all render without 500s.
  - Strategy dropdown includes both static and any new strategies from analytics.

---

#### 2.6 `lifecycle.json`

- **Path**: `<POLYMARKET_DATA_PATH>/lifecycle.json`
- **Produced by**: `evaluate_strategy_lifecycle.py` in polymarket-alerts.
- **Consumed by**:
  - `app.utils.polymarket.get_lifecycle_json()`
  - `app.utils.polymarket.get_lifecycle_file_age()`
- **Primary routes / pages**:
  - `/polymarket/lifecycle`

**Expected structure (high level)**

- A JSON object with keys such as:
  - `strategies` (per-strategy verdicts and metrics)
  - `thresholds_used`
  - `generated_at`
- Templates operate on these fields but are guarded; missing keys typically produce empty tables with explanatory text.

**Missing / stale / invalid handling**

- If `lifecycle.json` is missing or unreadable:
  - `get_lifecycle_json` returns `None`.
  - Lifecycle tab shows an empty or explanatory state instead of crashing.

**Producer / consumer drift risks**

- Changing nested field names can hide specific table columns but should not 500 as long as the top-level type remains a dict.

**What to test after producer changes**

- Run `evaluate_strategy_lifecycle.py` to refresh `lifecycle.json`.
- Open `/polymarket/lifecycle`:
  - Confirm verdict rows render and strategy filters work.

---

#### 2.7 `polymarket_alerts.log`

- **Path**: `<POLYMARKET_DATA_PATH>/polymarket_alerts.log`
- **Produced by**: polymarket-alerts main loop logging.
- **Consumed by**:
  - `app.utils.polymarket.get_last_loop_time()`
  - `app.utils.polymarket_health.get_polymarket_freshness()` (via `last_loop_run`)
- **Primary routes / pages**:
  - `/polymarket/portfolio` (header “polymarket-alerts last run: X ago”)
  - `/polymarket/loop` (Loop / Dev header)
  - Health JSON endpoints.

**Expected format**

- Lines containing `LOOP SUMMARY` with a prefix timestamp:
  - Example pattern: `YYYY-MM-DD HH:MM:SS,... | INFO | === v6.0 LOOP SUMMARY ===`
  - Consumer uses a regex anchored at the line start to extract `YYYY-MM-DD HH:MM:SS`.

**Missing / stale / invalid handling**

- If the file is missing or no matching lines are found:
  - `get_last_loop_time` returns `None`.
  - UI shows “log not found” or omits the “last run” label.

**Producer / consumer drift risks**

- Changing the log line **prefix format** (before `LOOP SUMMARY`) can prevent the regex from matching, making MiniStatus think the loop has never run.
- Removing `LOOP SUMMARY` markers entirely will have the same effect.

**What to test after producer changes**

- Run at least one polymarket-alerts main loop that logs a LOOP SUMMARY.
- Confirm:
  - Portfolio and Loop / Dev tabs show a recent “last run” message.
  - `/polymarket/health` and `/polymarket/freshness` include a non-null `last_loop_run`.

---

#### 2.8 `interesting_positions.json`

- **Path**: `<POLYMARKET_DATA_PATH>/interesting_positions.json`
- **Produced / mutated by**: MiniStatus via:
  - `app.utils.polymarket.get_interesting_ids()`
  - `app.utils.polymarket.toggle_interesting()`
- **Consumed by**:
  - `app.utils.polymarket.get_interesting_ids()`
  - `/polymarket/positions` (Open Positions tab; interesting filter/toggle)

**Expected structure**

- JSON object with shape (MiniStatus writes this):
  - `{ "market_ids": ["id1", "id2", ...] }`

**Missing / stale / invalid handling**

- If file is missing:
  - Treated as empty set; all positions start as “not interesting”.
- If malformed:
  - Reader returns empty set rather than raising; toggles may re-create a clean file.

**Producer / consumer drift risks**

- This file is primarily a **consumer-side preference store**; drift only matters if polymarket-alerts starts managing or relying on it, which it currently does not.

**What to test after changes**

- From the Open Positions tab:
  - Toggling “interesting” status for a position:
    - Updates UI immediately.
    - Persists across page reloads.

---

### 3. Health and Freshness Endpoints (for Monitoring)

MiniStatus exposes integration-focused JSON endpoints under the Polymarket blueprint:

- **`GET /polymarket/health`**
  - Backed by `app.utils.polymarket_health.get_polymarket_health()`.
  - Returns:
    - `configured` (bool)
    - `alerts_schema_ok` (bool)
    - `alerts_schema_error` (string or null)
    - `freshness`:
      - `alerts_log_age`
      - `open_positions_age`
      - `debug_candidates_age`
      - `analytics_age`
      - `lifecycle_age`
      - `last_loop_run`
  - Always returns **200** with a JSON body (even when misconfigured) so monitoring systems can alert on fields, not status codes.

- **`GET /polymarket/freshness`**
  - Backed by `app.utils.polymarket_health.get_polymarket_freshness()`.
  - Returns:
    - `configured` (bool)
    - `freshness` as above (without schema flags).

These are the preferred probes for **integration reliability checks**:

- Alert when:
  - `configured == false` (data path misconfigured or missing).
  - `alerts_schema_ok == false` (alerts_log schema drift).
  - Any critical file age exceeds your SLO (e.g. `alerts_log_age` older than 15–30 minutes).

---

### 4. Summary: What to Re-Test When polymarket-alerts Changes

Whenever the producer (`polymarket-alerts`) changes anything related to:

- `alerts_log.csv` schema or writing logic
- `open_positions.csv` schema or writing logic
- `debug_candidates*.csv` schema or naming
- `analytics.json` / `lifecycle.json` exporters
- main loop logging format for `polymarket_alerts.log`

You should:

1. **Verify on the producer side**
   - Run its own validators and exporters (e.g. `validate_alerts_log.py`, `analytics_export.py`, `evaluate_strategy_lifecycle.py`, `log_run_stats.py`, etc.).
2. **Probe MiniStatus integration health**
   - `GET /polymarket/health`
   - `GET /polymarket/freshness`
3. **Spot-check MiniStatus UI**
   - Portfolio, Open Positions, Risky, Loss Lab, Analytics, Lifecycle, Loop / Dev tabs all render without errors and show plausible data.

This ensures consumer-side reliability without requiring changes to MiniStatus for each producer iteration, as long as the above contracts remain intact.

