# Claude-Modified Changes

> This file tracks all changes made with Claude Code assistance.
> Only Polymarket-related work is listed here — the core MiniStatus app predates this collaboration.
> Entries grouped by feature area. Dates are commit dates (UTC).
> Uncommitted work-in-progress is at the bottom.

---

## Committed Changes

### Fix: Stale Analytics Warning & Simulated Bets Display (2026-03-20)
- `app/utils/polymarket.py` — suppress stale analytics warning when data is fresh; preserve strategy filter across navigation
- `app/routes/polymarket.py` — show `status=sent` (simulated bets) in Recent Decisions panel
- `app/templates/polymarket.html` — clarify Analytics tab copy

### Cross-Repo Synthesis Docs (2026-03-20)
- `docs/CONTEXT.md` — link to polymarket-alerts cross-repo synthesis doc
- `docs/polymarket.md` — note upstream `alert_id` resolution matching + repair

### Portfolio: bet_size_usd + conviction_score Columns (2026-03-19)
- `app/utils/polymarket.py` — expose `bet_size_usd` and `conviction_score` from alerts_log
- `app/templates/polymarket.html` — Portfolio tab shows bet size and conviction per decision

### Polymarket UX: Bankroll + Command Center Panels (2026-03-19)
- `app/templates/polymarket.html` — bankroll summary panel (deployed/available/total)
- `app/templates/polymarket.html` — command center panel (one-liner service restart commands)
- Fixed Jinja dict access bug (`.get()` vs `[]`)

### Live Status Mix Panel (2026-03-19)
- `app/utils/polymarket.py` — `get_status_mix()`: counts sent/shadow/blocked by strategy per loop
- `app/templates/polymarket.html` — Live Status Mix panel showing top block reasons

### Release 1.5.0: Strategy Labels, Data Quality Banners, Fill Quality (2026-03-17)
- Strategy mode labels (active/shadow/disabled) in dropdown
- Data quality banners for stale or missing data files
- Fill quality card (slippage metrics from execution_log.csv)
- Cohort matrix card (strategy family vs. conviction tier breakdown)
- Positions tab: refresh live pricing button
- Filter bar refresh UI

### Strategy Dropdown: safe_fast, safe_premium, safe_swing_low_gamma (2026-03-17)
- `app/utils/polymarket.py` — added new cohort strategies to dropdown

### Section Dividers & Path Refresh (2026-03-17)
- `app/routes/polymarket.py` — section dividers between tab groups
- Updated all script paths to match `jobs/` and `analytics/` restructure in polymarket-alerts

### Consumer Integration Docs & Health Endpoints (2026-03-16)
- `docs/INTEGRATION_GUIDE.md` — consumer integration guide aligned with producer contract
- `app/routes/polymarket.py` — `/health` endpoint for integration contract verification

### Release v1.4.0: Polymarket Dashboard Improvement Plan EPICs 1–4 (2026-03-14)
- **EPIC 1** — Analytics tab: strategy-level P/L breakdown, edge/gamma distribution
- **EPIC 2** — Risky tab improvements: filter, sort, flag logic
- **EPIC 3** — Loss Lab tab: loss pattern analysis
- **EPIC 4** — Lifecycle tab: strategy lifecycle verdicts display
- Fixed 500 errors on missing/malformed data files

### Repo Cleanup: remove redundant reference docs (2026-03-07)
- Removed stale polymarket-alerts reference docs copied into MiniStatus

### Analytics & Lifecycle Tabs (2026-03-07)
- `app/routes/polymarket.py` — `/analytics` and `/lifecycle` routes
- `app/utils/polymarket.py` — read analytics.json and lifecycle.json
- `app/templates/polymarket.html` — Analytics and Lifecycle tab UI
- File age display for all data files

### Risky Tab & Restart Script (2026-03-05)
- `app/routes/polymarket.py` — `/risky` route to track interesting positions
- `scripts/restart_polymarket.sh` — helper restart script

### Configurable Debug Candidates CSV (2026-03-03)
- `app/utils/polymarket.py` — read `DEBUG_CANDIDATES_CSV` env var for debug tab

### v1.3.0: Polymarket UX Refactor (2026-03-02)
- Full Polymarket section refactor: routes, templates, utils split
- Improved error handling for missing/empty data files
- Docs updates

### Losses, Unresolved, Live Prices, Edge/Gamma Bands (2026-03-01)
- `app/templates/polymarket.html` — Losses tab and Unresolved tab
- Live price refresh on Positions tab
- Edge/Gamma band filter for candidates

### Add Polymarket Integration (2026-02-28)
- `app/routes/polymarket.py` — Polymarket section blueprint
- `app/utils/polymarket.py` — read alerts_log.csv, bankroll.json, open_positions.csv
- `app/templates/polymarket.html` — Portfolio, Candidates, P/L chart tabs
- Gunicorn config for production serving

---

## Uncommitted Changes (current working state — 2026-03-31)

### AI Simulation Tab (`app/templates/polymarket_ai_simulation.html` — new file)
- New tab: shows `status=ai_sim` rows from alerts_log.csv
- Filter + sort UI; reads AI bankroll from `ai_sim_bankroll.json`
- Route: `/polymarket/ai-simulation`

### AI Performance Tab (`app/templates/polymarket_ai_performance.html` — new file)
- New tab: accuracy analysis for the AI screener
- Shows verdict/confidence breakdown; resolution outcome cross-tab
- Highlights SKIP+High confidence saves vs. false positives
- Route: `/polymarket/ai-performance`

### AI Data Functions (`app/utils/polymarket.py`)
- `get_ai_performance()` — joins `ai_verdict`/`ai_confidence` with resolved P/L; computes screener accuracy by tier
- `get_ai_sim_stats()` — reads `ai_sim` rows and `ai_sim_bankroll.json` for the AI Simulation tab
- `blocked_ai_screen` counted in status_mix summary

### New Routes (`app/routes/polymarket.py`)
- `/polymarket/ai-simulation` — AI Simulation tab
- `/polymarket/ai-performance` — AI Performance tab
- Both tabs added to sidebar navigation

### Base Template Navigation (`app/templates/base.html`)
- AI tab group added to Polymarket sidebar

### Daily Notes (`docs/daily/2026-03-29.md`)
- Session notes: API cost investigation, model switch Sonnet → Haiku, cap debug

---

## Session 2026-04-16 (Mirror poll groups + Portfolio fixes)

### Mirror alerts (split timers)
- `app/templates/polymarket_mirror_alerts.html` — `poll_group` on add + table column + auto-submit change
- `app/routes/polymarket.py` — `set-poll-group` route; `MIRROR_POLL_GROUPS`, `normalize_mirror_poll_group`
- `app/utils/polymarket.py` — `save_mirror_watch_config` / `get_mirror_watch_config` preserve `poll_group` and `min_notional_usd`

### Portfolio / status panel
- `get_recent_decisions(..., strategy=...)` — aligns with portfolio nav filter
- `get_alerts_status_summary` — `blocked_risk_limit`, `blocked_ai_screen`, `top_risk_buckets` for `polymarket.html`

### Upstream (polymarket-alerts repo)
- `core/mirror_watch_config.py` — `poll_group`, `filter_wallets_for_poll_group`
- `jobs/mirror_watch.py` — `--poll-group`
- `systemd/*mirror-watch*` split units + `systemd/README.md`

### Docs / release notes
- `CHANGELOG.md` **[1.5.2]**, `docs/MINISTATUS_INTEGRATION.md` (mirror JSON + split timers)
