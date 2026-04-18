# Changelog

All notable changes to MiniStatus are documented in this file.

## [1.6.0] - 2026-04-18

### Added

- **Phase 5 Chunk 5a — global safe scope:** `polymarket_safe_scope` in the Flask session, set from `?safe_scope=` on Polymarket routes and used when the query param is omitted. **Portfolio** (stats, recent decisions, CSV export) and **top section nav** use the same scope as Scorecard / AI Simulation.

### Changed

- **`get_polymarket_stats` / `get_recent_decisions`:** optional `safe_scope='safe_only'` filters rows to the safe-execution sport allowlist (same semantics as the scorecard).

---

## [1.5.9] - 2026-04-18

### Changed

- **Phase 1.5 (Tier 2) — Polymarket operator console:** MiniStatus is now positioned as the read-only console for `polymarket-alerts`. Legacy **service monitor** UI is removed from the product surface; **no Python modules are deleted** (single `git revert` can restore blueprints).
- **`app/templates/base.html`:** Sidebar shows **Polymarket** (collapsible, **Scorecard** first) + **Settings** (password, API test) + **Logout**; legacy links (public dashboard, ports, admin services dashboard, remote, tags, auto-tag rules) removed. Logo points to the scorecard.
- **`app/routes/public.py`:** `GET /` → `302` → `/polymarket/scorecard`. `/feed.xml` and `/rss` → `404`.
- **`app/__init__.py`:** Unregistered blueprints `sync`, `remote`, `ports`, `api` (CSRF exempt removed with `api`).
- **`app/routes/admin.py`:** `/admin/` → redirect to scorecard; login / password-change success → scorecard; service/tag/auto-tag CRUD routes return **404** via `_legacy_service_monitor_gone`.

---

## [1.5.8] - 2026-04-18

### Added

- **Scorecard (Chunk 1d):** “See full scorecard →” on Portfolio (Strategy Overview details + Pipeline card when overview is empty) and AI Simulation (below KPI cards; respects `safe_scope` / `days`). Nav order unchanged — Scorecard remains first via `POLYMARKET_SECTIONS` (comment in `polymarket_nav.html`).

---

## [1.5.7] - 2026-04-18

### Added

- **Scorecard (Chunk 1c):** `polymarket_scorecard.html` — table (sent / resolved / wins / losses / win rate / realized PnL / ROI / last sent), scope + time window (All / 7d / 30d), sortable column headers (default realized PnL desc), insufficient-sample badge + muted win rate/ROI. Default response is HTML; `format=json` for API. **Scorecard** is the first Polymarket nav item.

---

## [1.5.6] - 2026-04-18

### Added

- **Scorecard (Chunk 1b):** `GET /polymarket/scorecard` — JSON list from `get_strategy_scorecard()`; query params `safe_scope` (default `safe_only`), optional `days`, `format=json` (default). `format=html` returns 501 until Chunk 1c.

---

## [1.5.5] - 2026-04-18

### Added

- **Scorecard (Phase 1, Chunk 1a):** `get_strategy_scorecard(data_path, safe_scope=…, days=…)` in `app/utils/polymarket.py` — read-only per-strategy aggregates over `alerts_log.csv` (`status=sent` only; resolved = truthy `resolved` + numeric `pnl_usd`). Tests in `tests/test_polymarket_scorecard.py`.

---

## [1.5.4] - 2026-04-18

### Added

- **AI Simulation — Safe-scope toggle:** new *Safe only* vs *All tracked* switch on the AI Simulation tab. When set to *Safe only* (default) the simulation stats, resolved/open markets, and pagination are restricted to sports on the shared safe-execution allowlist (`SAFE_EXECUTION_SPORTS`, default `soccer,tennis,nba,nhl,mlb`). The selection persists across refresh, filter, sort, and pagination via a `safe_scope` query parameter.
- **`polymarket_constants.py`:** new block-reason label `sport_not_enabled_for_safe_execution` → "Sport not enabled for safe execution"; extended `SPORT_DISPLAY_LABELS` with `tennis`, `golf`, `mma`, `boxing`, `esports`, `american_football`, `other`.
- **`app/utils/polymarket.py`:** `_safe_execution_sports()` helper (env-backed) and `get_ai_sim_stats(safe_scope=…)` filtering.

---

## [1.5.3] - 2026-04-17

### Added

- **Portfolio / Polymarket UI:** optional **Sport** and **Type** columns when `sport` and `market_type` are present in `alerts_log.csv`; bankroll summary includes **by-sport** open exposure (`sport_open`).
- **`polymarket_constants.py`:** strategy labels and block-reason strings for safe NBA/NHL/MLB lanes and sport caps (`blocked_sport_cap`, `blocked_event_duplicate`).

### Fixed

- **Sidebar navigation:** main nav scrolls (`flex` + `overflow-y-auto`) when the Polymarket submenu is expanded.
- **Tab navigation:** preserve main content scroll position across Polymarket section changes via `sessionStorage.polymarket_scroll` in `base.html` (strategy links in `polymarket_nav.html`); removed duplicate scroll handlers from individual templates; Sort `<select>` elements no longer use `data-polymarket-nav` (avoids conflicting with strategy navigation).

### Documentation

- **`docs/POLYMARKET_INTEGRATION.md`** — extended header note (`event_key`); UI scroll behavior.

### Notes (upstream)

- **polymarket-alerts** `v6.6.0`: `alerts_log.csv` schema v7 adds **`event_key`**; run **`scripts/backfill_alert_metadata.py`** on existing logs if you want historical rows populated. Copy `polymarket-alerts/docs/alerts_log_header.json` to **`tests/fixtures/alerts_log_header.json`** when syncing schema (see integration contract checklist).

---

## [1.5.2] - 2026-04-16

### Added

- **Polymarket: Mirror alerts poll groups** — Per-wallet `poll_group` (`standard` | `fast`) in `mirror_watch_config.json`; Mirror alerts UI (add form, per-row dropdown, `POST /polymarket/mirror-alerts/set-poll-group`). Use with polymarket-alerts **split** mirror timers (`--poll-group standard` vs `--poll-group fast`); see upstream `systemd/README.md`.
- **`get_recent_decisions(..., strategy=...)`** — When the nav strategy is not `all`, recent decisions are filtered to that `strategy_id`.

### Changed

- **`get_alerts_status_summary`** — Adds `blocked_risk_limit`, `blocked_ai_screen`, and `top_risk_buckets` for the Portfolio status panel (`polymarket.html`).

### Fixed

- **Polymarket Portfolio 500** — Removed `TypeError` from `strategy=` on `get_recent_decisions`; removed Jinja `UndefinedError` for missing `status_summary.blocked_risk_limit` (and related keys).
- **`app/utils/polymarket.py`** — Ensures the AI tab / schema bundle is present (`get_ai_performance`, `get_ai_sim_stats`, `collect_json_artifact_schema_warnings`, live loop diagnostics). Avoid partial edits that drop this block (app will not boot).

---

## [1.5.1] - 2026-04-13

### Changed

- **Polymarket `alerts_log.csv` schema messaging** — When required columns are missing and the CSV has **≤3** header columns, `validate_alerts_log_schema` appends a **non-canonical header** hint: check `POLYMARKET_DATA_PATH`, run **`polymarket-alerts`** `scripts/validate_alerts_log.py --csv ... --repair`, and note **`alerts_log.csv.bak.noncanonical`**. Aligns with upstream **polymarket-alerts v6.4.1** (header guard in `validate_alerts_log.py`).

### Documentation

- **`docs/POLYMARKET_INTEGRATION.md`** — Troubleshooting for junk / non-canonical `alerts_log.csv` headers and recovery.

---

## [1.5.0] - 2026-03-17

### Added

- **Polymarket: strategy labels and mode** — `STRATEGY_LABELS` and `STRATEGY_MODE` in `app/utils/polymarket.py`; exposed as Jinja globals so templates show human-readable strategy names (e.g. "Safe fast") and mode badges (active / shadow / legacy) in the dropdown, Portfolio table, and Open Positions table.
- **Polymarket: data quality banners** — `app/utils/data_quality.py` checks unrealized P/L (all zero → live pricing hint) and drift data sparsity; banners rendered below the Polymarket nav on all Polymarket tabs.
- **Polymarket Analytics: fill quality card** — New card from `analytics.json` `fill_quality`: note, avg fill gap, and table by spread bucket (tight/narrow/medium/wide).
- **Polymarket Analytics: cohort matrix** — Gamma × resolution-window heatmap from `analytics.json` `cohort_matrix`; cells show total P/L, win rate, n; green/red by sign; low-data cells faded.
- **Polymarket Open Positions: live pricing on refresh** — Refresh form includes "Live prices" checkbox; when checked, refresh runs `update_open_positions.py` without `--no-live` so unrealized P/L is updated from the API.
- **Polymarket Open Positions: price staleness** — Unrealized P/L card shows "Prices as of: YYYY-MM-DD HH:MM" when `last_price_refresh_ts` is present; hint text updated for refresh + "Fetch live prices".
- **PROJECT_STRUCTURE.md** — Compact directory tree and Polymarket data sources at repo root.

### Changed

- **Polymarket Open Positions: refresh control placement** — "Refresh positions" and "Live prices" checkbox moved from the top-right (next to Strategy dropdown) into the filter bar with Time window, Category, Track, Hrs left, and Sort, labeled "Refresh:" for clearer context.
- **Polymarket routes: section comments** — Added section dividers in `app/routes/polymarket.py` (Health, Portfolio, Positions, Risky, Loss Lab, Analytics, Lifecycle, Loop, Export) for easier navigation.
- **Polymarket CSV schema mismatch** — `alerts_log.csv` is now read with `utf-8-sig` (strip BOM) and, when required columns are missing, CSV delimiter is auto-detected (e.g. semicolon) so Excel-exported or locale-different files are accepted. Portfolio and Loss Lab error messages now suggest checking `POLYMARKET_DATA_PATH` and running `python scripts/validate_alerts_log.py --csv alerts_log.csv` in polymarket-alerts to validate or repair.

---

## [1.4.0] - 2026-03-14

Polymarket Dashboard Improvement Plan (EPICs 1–4): Loss Lab v2 (breakdowns, monthly trend, examples UX), Risky v2 (historical performance, presets, Near Risky, qualified reasons, unrealized P/L messaging), Lifecycle v2 (purpose banner, progress column, HOLD actionable text, event log, strategy filter), cross-tab freshness (all tabs show last updated), strategy filter on Analytics/Lifecycle, normalized terminology, drill-down links, metric tooltips (inlined). Fixes: Analytics and Risky 500 (tooltips partial removed, analytics dict normalization, Risky datetime/empty-historical, Analytics template nesting). See [Unreleased] below for full item list.

---

## [Unreleased]

### Added (2026-04-05)

- **Polymarket: Mirror Portfolio** — Tab `/polymarket/mirror-portfolio`: reads `mirror_portfolio.json` from `POLYMARKET_DATA_PATH`; wallet + days form; POST refresh runs `analytics/mirror_portfolio_export.py` (CSRF-protected); sidebar link.
- **Polymarket: Mirror alerts** — Tab `/polymarket/mirror-alerts`: manage up to **20** watched wallets (address, label, Telegram on/off, remove); reads/writes `mirror_watch_config.json` on the data directory; sidebar link. Separate from Mirror Portfolio to keep alert routing vs analytics separate.
- **`app/utils/polymarket.py`** — `get_mirror_portfolio_json`, `get_mirror_portfolio_file_age`, `get_mirror_watch_config`, `save_mirror_watch_config`, `MIRROR_WATCH_MAX_WALLETS`.
- **Tests** — `tests/test_polymarket_mirror_portfolio.py`, `tests/test_polymarket_mirror_watch_config.py`.

### Changed

- **Polymarket Analytics vs Portfolio** — `analytics_export.py` (upstream) now counts resolved P/L for **`status=sent` only**, same as Portfolio. Regenerate `analytics.json` after upgrading polymarket-alerts. Analytics tab copy notes this; **data quality** warns when the live log has **no** sent+resolved rows but `analytics.json` cohort still shows resolved trades (stale JSON or empty log).
- **Sidebar Polymarket links** — Preserve `?strategy=` when switching sections from the left nav (same as the tab bar).

### Notes (upstream polymarket-alerts)

- **Resolution CSV matching** — polymarket-alerts `jobs/resolution_tracker.py` now updates the correct `alerts_log.csv` row using `alert_id` (not the first row with the same `token_id`). If Portfolio showed “stuck” `sent` rows while `blocked_*` lines had P/L for the same market, upgrade polymarket-alerts and run `scripts/repair_duplicate_token_resolutions.py` then `jobs/resolution_tracker.py --once` on the data directory (see polymarket-alerts `docs/RUNBOOK.md`).

### Added

- **Polymarket status-mix panel (backend v6.5 sync)** — Portfolio now shows a compact "Live status mix" panel sourced from `alerts_log.csv`: Logged, Sent, Shadow, Blocked, explicit `blocked_inactive_strategy` count, and top block reasons from `primary_block_reason`. This keeps MiniStatus aligned with polymarket-alerts dynamic sizing/risk telemetry and makes capacity/policy bottlenecks visible without reading Telegram logs.
- **Polymarket UX readability pass** — Default strategy selection to first active (not `safe`), group strategy dropdown by mode (active/shadow/probes/disabled), add Portfolio + Positions bankroll widgets from `bankroll.json`, add Portfolio "Strategy Overview" command center from `strategies.yaml`, humanize block-reason labels + improve status mix copy, add tooltips + subtle shadow-row tint in resolved lists, and improve Lifecycle empty-state + add a "What does this tab do?" help block.
- **Polymarket decision trace in UI** — Portfolio adds a collapsible "Recent decisions" table showing per-alert `bet_size_usd` and `conviction_score` alongside status + primary block reason.
- **Polymarket portfolio betting trace** — Portfolio resolved alerts table now includes `bet_size_usd` ("Bet size") and `conviction_score` ("Conv.") columns for placed (`sent`) alerts, so you can see exactly how much was bet for each resolved outcome.

- **Analytics tab v2 (decision-oriented)** — **Insights block** at top: suggested min edge, best timing windows, top strategy by ROI, drift status. **Edge Quality:** Win rate %, Median P/L per trade, Confidence (Low/Medium/High), suggested edge threshold note. **Timing:** same columns + best hold windows note. **Strategy Cohort:** Win rate %, Median P/L, Confidence, Status (Promising / Weak / Too Early / Neutral) with muted badges. **Drift Study:** per cell shows avg drift, positive %, n; tooltip for median and positive % meaning. All new fields show "—" when missing; no layout or breakage on old analytics.json.

- **Analytics: "Why 0 drift?" note** — When execution log has rows but no drift data (1m/5m/… all 0), the Post-Alert Midpoint Drift section now shows a short in-UI explanation: drift is filled only when backfill runs while an alert is in the time window (e.g. 1–6 min for 1m); old alerts never enter those windows, so new alerts are needed for drift to populate.

- **Loss Lab: breakdowns by edge, gamma, and timing buckets** — Loss Lab now includes four additional sections showing how realized losses cluster by edge buckets (<0.5%, 0.5–1.0%, 1.0–1.25%, 1.25%+), gamma buckets (<0.80, 0.80–0.90, 0.90–0.94, 0.94+), hold-duration buckets (Same day, 1–3d, 3–7d, 8–10d, 10+d), and time-to-resolution buckets (same as Analytics timing). All breakdowns are computed from resolved losing alerts in `alerts_log.csv`, respect the Loss Lab time window and strategy filters, and are purely additive to the existing category cards.

- **Loss Lab: monthly trend view** — Added a Monthly Trend section showing net P/L per month, broken down by category, using resolved alerts from `alerts_log.csv`. The trend respects the Loss Lab time window and strategy filters and highlights both negative and positive months, making it easy to see whether losses are getting better or worse over time.

- **Loss Lab: examples UX** — For the worst-loss category card, examples are now expanded by default with a small “Examples (worst losses)” section. Other categories keep a compact “Show examples (N)” toggle. This keeps the page uncluttered while surfacing the most important loss examples without extra clicks.

- **Risky: historical performance section** — Risky tab now shows **Risky historical performance**: resolved alerts that would have qualified as Risky (same edge/gamma/expiry thresholds), with qualifying count, win rate, realized P/L, ROI, avg edge, avg gamma, avg hold duration, and a by-category table. Uses `alerts_log.csv`; respects the tab's time window and strategy filter.

- **Risky: classification reasons per row** — Each risky position row now has a **Qualified** column with a "Why?" hint; hover shows the three rules that admitted the row: edge ≥ threshold, gamma ≤ threshold, expiry ≤ threshold (with actual values).

- **Risky: threshold presets** — Preset buttons **Env**, **Conservative**, **Default**, **Loose** on the Risky tab. Conservative: edge ≥ 1.25%, gamma ≤ 0.90, expiry ≤ 24h. Default: 1%, 0.94, 48h. Loose: 0.5%, 0.97, 72h. Env uses `RISKY_*` env vars. Switching preset updates the position list and historical performance section; preset is preserved in time-window, sort, and filter links.

- **Risky: Near Risky section** — A **Near Risky** table lists open positions that narrowly miss one threshold (edge within 0.25%, gamma within 0.02, expiry within 12h). Each row shows which threshold was missed (edge / gamma / expiry). Helps distinguish an empty tab because nothing is close from one where many positions barely miss.

- **Risky: unrealized P/L fallback messaging** — When Unrealized P/L shows "—", the KPI card now shows: "Live unrealized P/L unavailable. Run Open Positions → Refresh with live pricing to populate." When a value is shown, a short note explains: "From last refresh; use Open Positions → Refresh for current prices." So users can tell missing live data from a bug.

- **Lifecycle v2 (governance)** — **3.1** Plain-language purpose banner: explains that Lifecycle evaluates shadow/active strategies and that shadow can be promoted and weak strategies flagged for kill. **3.2** Threshold progress: new Progress column shows resolved X / kill threshold, X / promotion threshold; for INSUFFICIENT_DATA shows "Need N more resolved to reach kill threshold." **3.3** HOLD actionable: for HOLD, shadow strategies see "N more resolved for promotion" and "ROI ≥ X% to promote"; active see "ROI above Y% to avoid kill." **3.4** Lifecycle event log: table structure (Date, Strategy, Previous, New status, Reason, Source) with empty state until apply_lifecycle_verdicts or overrides are recorded.

- **EPIC 4.1 — Freshness on every tab** — Portfolio shows alerts_log last updated; Open Positions and Risky show open_positions.csv last updated; Loss Lab shows alerts_log; Loop shows debug_candidates.csv. Analytics and Lifecycle already showed analytics.json and lifecycle.json age. New helper `get_file_age(data_path, filename)` in polymarket utils. Users can tell stale data from broken logic.

- **EPIC 4.2 — Strategy filter meaningful on every tab** — Strategy dropdown now filters data on Analytics and Lifecycle. **Analytics:** Strategy Cohort and Post-Alert Midpoint Drift tables show only the selected strategy when a strategy is chosen; Edge Quality and Timing remain global with a note that Cohort/Drift are filtered. **Lifecycle:** Verdicts table shows only the selected strategy when chosen. Empty states show “No cohort/drift/verdict for strategy X” when filtered and missing. Refresh forms on Analytics and Lifecycle pass strategy as hidden input so redirect preserves the selected strategy after refresh.

- **EPIC 4.3 — Normalized terminology** — Time window labels are consistent across tabs: "All time", "Last 30 days", "Last 90 days", "Last 180 days" (via shared `polymarket_time_filter.html`). Edge/gamma/hold bucket names come from a single backend definition in polymarket utils; same vocabulary on Analytics, Loss Lab, and Risky.

- **EPIC 4.4 — Drill-down links** — **Lifecycle → Analytics:** Strategy name in verdicts table links to Analytics filtered to that strategy. **Analytics → Lifecycle:** Strategy name in Strategy Cohort links to Lifecycle filtered to that strategy. **Analytics → Loss Lab:** "Weak" status badge in Strategy Cohort links to Loss Lab filtered to that strategy. **Risky → Portfolio:** Category in Risky historical performance table links to Portfolio (filter=losses, same category/days/strategy). Loss Lab category cards already linked to Portfolio (View in Portfolio).

- **EPIC 4.5 — Metric tooltips** — New shared partial `polymarket_tooltips.html` with definitions for Edge, Gamma, Drawdown, Confidence, ROI, Median P/L, Avg hold, Total P/L. Table headers on Analytics (Edge Quality, Timing, Strategy Cohort, Drift), Loss Lab (edge/gamma/hold/ttr buckets), Lifecycle (ROI %, Total P/L), and Risky (Gamma, Edge) show tooltips on hover so non-experts can understand the UI faster.

### Fixed

- **Risky tab 500** — Defensive template and data fixes: (1) Qualified column title uses `(p.edge or 0)` and `(p.gamma if p.gamma is not none else 0)` so None values do not raise. (2) Empty `risky_historical` dict from `get_risky_historical_performance()` now includes `total_pnl_display` and `total_cost_display` so template never sees missing keys. (3) Added `tests/test_polymarket_risky.py` to verify Risky template renders with minimal context (run with Flask env: `pytest tests/test_polymarket_risky.py -v`).

- **Analytics and Risky 500 (missing tooltips partial)** — Removed dependency on `polymarket_tooltips.html` from Analytics, Risky, and Loss Lab templates. Tooltip text is inlined in each template so the tabs work even when the partial is missing (e.g. after partial deploy). Guarded Analytics totals block with `analytics and analytics.get('totals')` to avoid errors when analytics is empty.

- **Risky tab 500 (AttributeError: datetime has no attribute strip)** — In `get_near_risky_positions()`, position dicts from `get_open_positions()` can have `alert_ts` as a `datetime` object. Building the risky-set key with `(p.get("alert_ts") or "").strip()` raised when `alert_ts` was a datetime. Fixed by normalizing with a small helper `_key_ts(v)` that returns `str(v).strip()` for strings and `str(v)` for other types (e.g. datetime), so keys are always strings. Removed temporary debug try/except that showed tracebacks in the browser.

- **Analytics tab 500 (strategy_cohort / exit_study not dict)** — If `analytics.json` had `strategy_cohort` or `exit_study` as non-dict (e.g. list or null from an old export), the template or `get_strategy_options_for_nav()` could raise (e.g. `.keys()` or `.items()` on non-dict). Fixed: (1) `get_strategy_options_for_nav()` now treats non-dict `strategy_cohort` as `{}`. (2) Analytics route normalizes `analytics` so `strategy_cohort`, `edge_quality`, `timing`, `exit_study`, and `insights` are always dicts (replaced with `{}` if present but not a dict) before passing to the template.

- **Analytics tab 500 (TemplateSyntaxError: nesting mistake)** — In `polymarket_analytics.html`, the Drift Study block used `{% if ex %}` and inside it `{% if ex_items %} … {% elif %} … {% else %} … {% endif %}` but the outer `{% if ex %}` was never closed, so Jinja expected `{% endif %}` and hit `{% endblock %}`. Fixed by adding the missing `{% endif %}` after the drift block so the template parses correctly.

- **Risky → Portfolio category links** — Category names (e.g. SPORTS, OTHER) in Risky historical performance now link to Portfolio with `#resolved-alerts` so the page scrolls to the filtered resolved list instead of opening at the top. Portfolio Resolved Alerts subtitle shows “category: X” when a category filter is applied.

- **Risky “Why?” tooltip** — Qualified column tooltip text clarified (e.g. “Hover: …”) and formatted on one line so the native browser tooltip shows reliably.

- **Loop/Dev: Hrs left column header** — The “Hrs left” table column header now **sorts** by hours left (click toggles soonest first ↔ latest first) instead of cycling the “Hrs left” filter. Filtering by range (All, ≤6h, ≤12h, etc.) remains in the bar above the table.

### Changed

- **Analytics: Post-Alert Midpoint Drift (Drift Study)** — Renamed from "MTM / Exit Study". Added interpretation: 1m/5m approximate (backfill uses current mid in window); 2h/1d more meaningful. UI now shows last backfill run (from `drift_summary.last_backfill_run`), execution row counts (total + per-horizon rows with drift data). Empty results easier to diagnose.

### Fixed

- **Loop/Dev: Hrs left for past events** — "Hrs left" was showing the value stored in the CSV at the time the main loop ran, so already-finished events still showed positive hours (e.g. 4.9h). Hrs left is now **recomputed from event_time at display time**. Past events show "Expired" and are excluded from the "Hrs left" filters (e.g. &lt;6h) so only future resolutions appear there.

- **Strategy preserved on filter/sort** – Portfolio, Open Positions, Risky, and Loss Lab now preserve the selected Strategy when changing time window, sort, category, or other filters (same fix previously applied to Loop/Dev).

### Removed

- **Polymarket Performance tab** – Removed in favor of **Analytics**. Analytics provides Edge Quality (edge buckets with ROI), Timing (time-to-resolution), Strategy Cohort (with drawdown), and MTM/Exit Study; Performance only added Expectancy by Gamma bands. Sidebar and tab nav no longer show Performance.

### Fixed

- **Loop/Dev tab: Resolution and Hrs left columns not visible**  
  The debug candidates CSV already contained `event_time` and `hrs_left` (written by polymarket-alerts main loop), but the Loop/Dev table did not display them. **Cause:** MiniStatus never read those columns or added table headers/cells for them. **Change:** In `get_debug_candidates()` we now read `event_time` and `hrs_left`, compute `resolution_display` (YYYY-MM-DD HH:MM) and `hrs_left_display` (e.g. `8.9h`, `2d`, or "Expired"), and in `polymarket_loop.html` we added **Resolution** and **Hrs left** columns after Question (same as Open Positions). Restart MiniStatus to pick up the change.

### Added

- **Polymarket Analytics and Lifecycle tabs** – **Analytics** tab: Edge Quality (by edge bucket), Timing (by time-to-resolution bucket), Strategy Cohort (per strategy with sent/shadow, resolved, open, W/L, P/L, ROI, current/max drawdown %), and MTM/Exit Study (per-strategy avg price move at 1m, 5m, 30m, 2h, 1d). **Lifecycle** tab: promote/kill verdicts per strategy (PROMOTE / HOLD / KILL / INSUFFICIENT_DATA) with reasons and thresholds. Data from `analytics.json` and `lifecycle.json` in POLYMARKET_DATA_PATH. **Refresh** buttons on both tabs run `analytics_export.py` and `evaluate_strategy_lifecycle.py` in the data path to regenerate JSON (uses venv python when present). **File age:** Analytics and Lifecycle pages show "Last updated: X min/hours/days ago" from file mtime when available.
- **Repo cleanup** – Removed redundant `docs/polymarket-alerts-CHANGELOG-update.md` and `docs/polymarket-alerts-README-update.md` (canonical docs live in polymarket-alerts repo).

- **Polymarket Strategy dropdown** – Options are now dynamic: merged from `STRATEGY_OPTIONS` and any strategy IDs present in `analytics.json` strategy_cohort, so new strategies from polymarket-alerts appear in the dropdown without code changes. Fallback remains the full list: safe, safe_v2, same_day_probe, hold_*_probe, gamma_*_probe, mid_gamma, resolution_sprint.

- **Polymarket debug candidates filename** – Loop/Dev tab reads the debug candidates CSV by name from `POLYMARKET_DEBUG_CSV` (default: `debug_candidates.csv`), with fallback to `debug_candidates_v60.csv` and then any `debug_candidates*.csv` for backward compatibility. Set to match polymarket-alerts `DEBUG_CANDIDATES_CSV` if you use a custom name.
- **Polymarket date/time filtering** – Standardized date format (YYYY-MM-DD HH:MM) across Portfolio, Open Positions, and Loop/Dev. Click any date cell to filter from that date. Time window filter (All time / Last 30/90/180 days) on Open Positions and Loop/Dev. Clickable "Opened" column header for sort; "Filter by opened" bar above positions table.

- **Polymarket Open Positions filters** – Time window (All time, Last 30/90/180 days), category filter (Politics, Sports, Crypto, Other), sort (cost, P/L, date, question). `open_positions.csv` now includes `alert_ts` from `alerts_log.csv` for date filtering.

- **Polymarket cross-tab UX** – Active tab styling (background, font weight), mobile horizontal scroll for tabs, loading overlay when switching tabs or applying filters, empty states (e.g. "No open positions", "No resolved alerts yet")

- **Polymarket Losses tab** – Dedicated tab for full loss list with category filter (Politics, Sports, Crypto, Entertainment, Other), display filter (All time / Last 30/90/180 days), sort (biggest first, date, question, by category), search, pagination, and Export Losses CSV.

- **Polymarket Unresolved tab** – Open positions (alerts not yet resolved). Shows at-stake total, sort by alert date or days to resolution, search, pagination. Optional **live prices** – click "Load live prices" to fetch current YES price from Polymarket CLOB API and display Entry, Live, and Unrealized P/L columns.

- **Polymarket Edge/Gamma bands** – Performance analytics by edge band (0–0.5%, 0.5–1%, 1–1.5%, etc.) and gamma band (0.90–0.95, 0.95–0.97, etc.). Shows count, win rate, and P/L per band. Respects Display filter.

- **Polymarket Loop Summary improvements** – Status filter (All / ALERT only), sort (date, edge, question, ALERT first), clickable column headers (Time, Question, Edge, Status), improved pagination with page numbers. Event time formatted as "Mar 02, 2026 05:30 PM UTC". Direct links to Polymarket markets (from debug CSV link column).

- **Polymarket Loop Summary tab** – New tab in Polymarket admin page displays full data from `debug_candidates_v60.csv` (same as "Full data" in Telegram loop summary). Paginated table with search, export CSV. Tabs: Resolved Alerts | Losses | Unresolved | Loop Summary.

- **Polymarket pagination** - Resolved alerts table paginated (50 per page) with Previous/Next, page numbers, and "Showing X–Y of Z" for better UX with many resolved alerts

- **Per-run stats log** - `scripts/log_run_stats.py` appends stats snapshot after each polymarket-alerts run to `run_stats.csv`; MiniStatus reads it and shows "Per-Run Stats Trend" charts (resolved count, P/L over time) for trend analysis

- **Polymarket sort options** - Resolved list sortable by P/L (lowest/highest first), date (newest/oldest), question (A–Z, Z–A), result (YES/NO first) for easier data exploration

- **Polymarket Integration** - Admin-only dashboard for polymarket-alerts
  - Summary stats: total alerts, resolved, wins, losses, net P/L
  - Filter by wins/losses (All / Wins / Losses)
  - Display filter: All time / Last 30 / 90 / 180 days
  - Client-side search by question text
  - Refresh button to reload data
  - Export CSV: download filtered list (question, result, pnl_usd, link)
  - Health check: "polymarket-alerts last run: X hours ago" from `polymarket_alerts.log`
  - P/L chart: cumulative P/L over time (Chart.js line chart)
  - Requires `POLYMARKET_DATA_PATH` in `.env` pointing to polymarket-alerts directory

- **Production WSGI** - Gunicorn instead of Flask dev server. Config in `gunicorn.conf.py`; workers, bind, and timeout configurable via env.

- **Backfill script** - `scripts/backfill_resolved_ts.py` – fills missing `resolved_ts` from `ts` for resolved rows (improves date filters and P/L chart)

- **Retention script** - `scripts/retention_alerts_log.py`
  - Trims `alerts_log.csv` to keep only rows from last N days
  - Creates `.bak` backup before modifying
  - Usage: `python3 retention_alerts_log.py --days 90 [--dry-run]`
  - Designed to be copied to polymarket-alerts and run via cron

### Changed

- **Unified admin_required decorator** – All admin-protected routes now use shared `app.utils.decorators.admin_required`; removed duplicate definitions from admin.py and sync.py
- **Polymarket refactoring** – Added `_polymarket_configured_required` decorator for not-configured handling; `_get_data_path()` helper; `build_pagination()` and `_STATS_EMPTY` in polymarket utils; shared `polymarket_time_filter.html` macro for time window UI; simplified `_parse_filter_days()` to return `(filter_val, days_val, days)`
- **403 error handler** – `errors_bp` now registered in app; custom 403 page renders when access is forbidden

### Removed

- **Unused files** – `polymarket_placeholder.html`, `public/home.html`, `scan_systemd.html`, `static/dark.css`
- **Dead code** – `register_blueprints()` from routes/__init__.py; `_bucket()` from polymarket utils; orphaned helpers (get_all_quick_links, get_security_summary, get_public_holidays, etc.) from helpers.py
- **Duplicate PORT_LABELS** – Removed from ports route; port labels come from port data
- **YAML config references** – `quick_links.yaml` and `security_summary.yaml` removed from docs (features were unused)
