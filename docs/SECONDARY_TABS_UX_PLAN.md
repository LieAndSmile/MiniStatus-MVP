# Secondary Tabs UX Plan (AI, Risky, Loss Lab, Analytics)

> Status: **planning reference** for the next agent/model to implement.
> Scope: improve readability and actionability of infrequently-used Polymarket pages. **Mirrors** (`mirror_portfolio`, `mirror_alerts`) is **out of scope** — do not touch.
> Goal: make each page answer a clear question in 5 seconds, reduce jargon, and surface the "what should I do with this" takeaway.

---

## 0. Ground rules

1. **No backend rewrites.** Everything here is Jinja templates + small helpers in `app/utils/polymarket.py` / `polymarket_health.py`. No new routes except as noted in §6 (optional).
2. **No schema changes** in polymarket-alerts except the **one** optional `analytics_prev.json` hook in §7.
3. **Do not modify** `polymarket_mirror_*.html` or `polymarket_mirror_*` routes.
4. **Keep top nav** at the current four tabs (Live, Scorecard, AI Simulation, Tools).
5. **Tests** — for each task below, run `.venv/bin/pytest -q` at the end. Smoke tests in `tests/test_polymarket_*` must stay green.
6. **After template edits**, restart the service: `sudo systemctl restart ministatus`.
7. **CHANGELOG** — add a short bullet under the current `[1.7.x]` section per task.

Related docs: `docs/POLYMARKET_INTEGRATION.md`, `docs/MINISTATUS_INTEGRATION.md`, `docs/DUCKDB_MIGRATION_PLAN.md`.

---

## 1. Priority order

Implement in this order. Each task ≈ 1–3 hrs. Land as separate commits so they can be reviewed / reverted independently.

| # | Task | Why first |
|---|---|---|
| 1 | **Shared page header partial** (§2) | Base building block used by every later task |
| 2 | **AI Simulation + AI Performance TL;DR + tooltips + sample size** (§3) | Highest confusion surface |
| 3 | **Risky: two-section split + summary strip** (§4) | Current layout conflates "now" and "historical" |
| 4 | **Loss Lab: biggest-driver cards + sparkline** (§5) | Converts raw numbers into actions |
| 5 | **Analytics: promote insights + Δ vs previous** (§6, §7) | Dense page; insights already computed but buried |

---

## 2. Task 1 — Shared secondary-page header

### Goal
One consistent header across `polymarket_risky.html`, `polymarket_loss_lab.html`, `polymarket_analytics.html`, `polymarket_ai_performance.html`, and `polymarket_ai_simulation.html` (Live/Scorecard stay as they are).

### Deliverable
New partial: `app/templates/_partials/polymarket_page_header.html`.

Signature (Jinja macro):

```jinja
{% macro page_header(title, purpose, freshness_label=None, freshness_value=None,
                     filter_slot=None, action_slot=None) -%}
  <section class="polymarket-page-header mb-6 ...">
    <div class="flex items-start justify-between gap-4 flex-wrap">
      <div>
        <h1 class="text-lg font-semibold ...">{{ title }}</h1>
        <p class="text-sm text-light-muted dark:text-dark-muted mt-1 max-w-2xl">{{ purpose }}</p>
        {% if freshness_label and freshness_value %}
        <p class="text-xs text-light-muted dark:text-dark-muted mt-2">
          <span class="font-semibold uppercase tracking-wider">{{ freshness_label }}</span>
          <span class="ml-2">{{ freshness_value }}</span>
        </p>
        {% endif %}
      </div>
      <div class="flex items-center gap-3">
        {{ action_slot }}
      </div>
    </div>
    {% if filter_slot %}
    <div class="mt-4 flex flex-wrap items-center gap-3" data-polymarket-filters>
      {{ filter_slot }}
    </div>
    {% endif %}
  </section>
{%- endmacro %}
```

### Rules
- **No logic inside** — the partial only renders what callers pass in.
- **Freshness** text comes from existing `data_freshness` / `analytics_age` variables — do not compute new ones.
- Filter slot is used for time-window chips, preset chips, etc. — do not invent new filters here.

### Steps
1. Create `app/templates/_partials/polymarket_page_header.html` with the macro.
2. Import from each target page with `{% from "_partials/polymarket_page_header.html" import page_header %}`.
3. Replace the ad-hoc intro blocks in each page with one `page_header(...)` call.
4. Visual check on all 5 pages. Nothing else should shift vertically more than ~8px.

### Tests
- Add a smoke test `tests/test_polymarket_shared_header.py` that GETs `/polymarket/risky`, `/polymarket/loss-lab`, `/polymarket/analytics`, `/polymarket/ai-performance`, `/polymarket/ai-simulation` as an authenticated session and asserts status 200 + `polymarket-page-header` string in body.

### Acceptance
- All 5 pages render with the new header, same freshness info, same filter controls.
- No regressions in existing `tests/test_polymarket_*` tests.

---

## 3. Task 2 — AI Simulation & AI Performance polish

### Files
- `app/templates/polymarket_ai_simulation.html`
- `app/templates/polymarket_ai_performance.html`
- (data) `app/utils/polymarket.py::get_ai_performance` / `get_ai_sim_stats` — **read-only reference**, do not change behavior.

### Deliverables

1. **TL;DR verdict card** at the top of each page.
   - Input: existing fields on `ai_perf` / `ai_sim`.
   - Output: one sentence + one headline number.
   - Example copy:  
     *"Of the last {{ n }} resolved bets, the AI blocked {{ m }}. Blocking saved approximately {{ "$%.0f"|format(saved_usd) }}. False-block rate: {{ fbr }}% (n={{ fbr_n }})."*
   - Color:
     - Green if `saved_usd > 0` **and** `fbr < 20`
     - Amber if `saved_usd > 0` **and** `20 <= fbr < 35`
     - Red if `saved_usd <= 0` **or** `fbr >= 35`
   - If `n < 30`, force colour = neutral, append `(low sample — treat as directional only)`.
   - Place **above** the existing metric grid. Do **not** delete the grid.

2. **Tooltips on every rate/metric.**
   - Edit each `<div>` metric tile to include `title="..."` on the **label span**.
   - Suggested tooltip text is in **§3.3** below; keep them short (< 140 chars).
   - Do not reorder tiles.

3. **Sample-size indicator next to every percentage.**
   - Append `(n=<count>)` when the value has a denominator. Reuse existing `ai_perf.lift_metrics.*_n` fields when present; if missing, add small helpers in `app/utils/polymarket.py` that read the same CSV already loaded by `get_ai_performance`.
   - Grey out (text-light-muted / dark-muted) when `n < 30`.

4. **Cross-link banner.**
   - On **AI Simulation** bottom: small card with link to AI Performance.
   - On **AI Performance** bottom: small card with link to AI Simulation.
   - Copy: *"Also see: AI Performance — how the AI screen actually scored on resolved bets."* (and vice versa).

5. **"What the AI screened out" table (AI Performance).**
   - Small table, last **5** rows where `ai_applied_effect=skip_*`, columns: time, question, strategy, AI verdict, resolved, outcome, P/L.
   - Data source: existing `alerts_log.csv` — add a helper `get_recent_ai_blocked(data_path, limit=5)` in `app/utils/polymarket.py`.
   - Keep it behind a `<details>` drawer (closed by default) so the page doesn’t grow tall.

### 3.3 Tooltip copy reference

```
false-block rate       → Blocked rows that later resolved YES (AI was wrong to skip).
loss-avoided rate      → Blocked rows that later resolved NO (AI correctly skipped).
SKIP High lift         → Extra win rate vs letting everything through, in percentage points, for the SKIP-HIGH tier.
SKIP Med lift          → Same as above for SKIP-MEDIUM tier.
ALLOW lift             → Win-rate of ALLOW rows minus win-rate of baseline (no AI gating).
producer policy        → Current mode in polymarket-alerts (shadow / gated / off).
last AI screen         → When polymarket-alerts last ran a screen (from producer config).
```

### Tests
- `tests/test_polymarket_ai_performance.py::test_tldr_renders_green_amber_red` — parametrize `saved_usd` / `fbr` into expected CSS class substring.
- `tests/test_polymarket_ai_blocked_recent.py::test_helper_returns_at_most_5` — unit-test the new CSV helper.

### Acceptance
- Page renders with TL;DR + tooltips + sample counts.
- Tiny sample (n<30) shows muted color and suffix.
- Cross-link present on both pages.

---

## 4. Task 3 — Risky split + summary strip

### File
`app/templates/polymarket_risky.html`.

### Deliverables
1. **Summary strip** directly below the shared header:
   - "Qualifying right now: **N** markets"
   - "Historical hit rate on same filter: **X%** (n=M)"
   - "Avg realized P/L per qualifier: **$Y**"
   - Source: existing `risky` / `risky_history` context variables. If the route doesn’t already return all three, add them in `polymarket_risky()` by reusing existing helpers (`get_risky_historical_performance`).

2. **Two clear sections** with their own headings:
   - `<section id="risky-now">` **Qualifying right now** — existing preset chips + list table.
   - `<section id="risky-history">` **Historical performance** — existing historical block, preceded by a one-line note: *"What would have happened if this filter had been live on past bets."*
   - Add a sticky table-of-contents chip row just under the summary strip: *"Jump: Now · History"* (plain anchor links to the sections).

3. **Empty state** when 0 markets qualify:
   - Replace the current empty table with a helper card showing current thresholds as big numbers and a **CTA** button linking to the **Loose** preset:  
     *"No markets match. Try a looser filter?"*.

4. **Row quick actions**: keep existing open-position link; add an **interesting toggle** (✶) consistent with `polymarket_positions.html`. The endpoint `polymarket_positions_toggle_interesting` already exists — call it via a small form per row.

### Tests
- `tests/test_polymarket_risky.py::test_summary_strip_contains_three_stats` — render with a fake context and assert presence of labels.
- `tests/test_polymarket_risky.py::test_empty_state_cta` — render with empty qualifying list and assert Loose preset URL appears.

### Acceptance
- Page shows the three summary numbers.
- Sections are explicit and anchorable.
- Empty state recommends Loose preset.
- Interesting toggle round-trips.

---

## 5. Task 4 — Loss Lab biggest-driver cards + sparkline

### File
`app/templates/polymarket_loss_lab.html`.

### Deliverables

1. **"Biggest drivers" card row** at the top (3 cards, grid):
   - **Worst category** — by total P/L loss over selected window.
   - **Worst strategy** — same.
   - **Worst timing bucket** — reuse `get_loss_breakdown_buckets`.
   - Each card: label (e.g. *"Politics"*), total loss (`$…`), secondary line (*"9 of 12 losers"*). Card links to the matching detail section on the same page (anchor).

2. **Monthly trend sparkline**.
   - Use the existing monthly-trend data already rendered on the page (search for "Monthly trend").
   - Add a **pure SVG** 200×40 line chart above the existing table.
   - No external libs. Stroke color = `currentColor` so it inherits theme.
   - Each x-tick = month label on hover (`<title>`).

3. **"What to do" explainer** under each breakdown section (one sentence each). Example: *"High loss density in a bucket suggests tightening edge in `strategies.yaml` for that bucket."*

4. **Filter chips** above the breakdown tables, generated from current params (category × time window × strategy). Clicking a chip removes it from the URL. Use existing `request.args`.

### Rules
- Do not touch `get_loss_breakdown*` return shapes.
- If the template needs a computed "top-3", add a small pure-function helper in `app/utils/polymarket.py::get_loss_top3_drivers(data_path, days, strategy)` that returns a dict `{category, strategy, timing_bucket}` — or compute inline in Jinja with `| sort(attribute='total_loss')`.

### Tests
- `tests/test_polymarket_loss_lab.py::test_top3_drivers_computed` — call helper (if added) with a crafted tmp CSV.
- `tests/test_polymarket_loss_lab.py::test_sparkline_svg_present` — GET page, assert `<svg` substring within monthly trend section.

### Acceptance
- Page shows 3 driver cards + inline sparkline.
- Chips remove individual filters without breaking pagination / defaults.

---

## 6. Task 5 — Analytics: promote insights + small charts

### File
`app/templates/polymarket_analytics.html`.

### Deliverables
1. **Hero insights card** at the top.
   - Use `analytics.insights.*` fields already returned by `get_analytics_json()`.
   - Render 3–4 bullets (suggested edge threshold, best timing windows, top strategy by ROI, drift status).
   - Include a small "Refresh analytics" button already present elsewhere; unify placement.
2. **Small SVG bars** for Edge Quality and Timing (replace raw tables with side-by-side bars).
   - Each row: label, value bar, % / count.
   - Accessibility: `<title>` on each bar; keep the underlying table in a `<details>` drawer for export.
3. **Section badges** for strategy filter.
   - When `current_strategy` is set and non-empty, render a small `STRATEGY` badge on the Cohort and Drift sections.
   - On Edge Quality and Timing sections render a `ALL STRATEGIES` badge.
4. **Downloads per section** (no route changes).
   - Each section: button linking to `/polymarket/export-debug?...` or `/polymarket/freshness` where applicable. If not applicable, render a client-side `Copy JSON` button with the section’s JSON payload inline in a `<script type="application/json">` tag.

### Tests
- `tests/test_polymarket_analytics.py` (new): render page with a tmp `analytics.json` fixture, assert hero card copy and SVG bars appear.

### Acceptance
- Hero card is the first thing on the page when insights exist.
- Edge Quality / Timing render as charts; details still available.

---

## 7. Task 5b (optional, producer-side) — Δ vs previous analytics.json

> **Only do this after tasks 1–5 are merged.** It requires a tiny change in polymarket-alerts.

### Producer change (polymarket-alerts)
1. In `analytics/analytics_export.py`, before writing `analytics.json`, if the old file exists, copy it to `analytics.prev.json` (same directory).
2. No schema change.

### Consumer change (MiniStatus)
1. Extend `get_analytics_json(data_path)` (or add `get_analytics_prev_json`) to optionally load `analytics.prev.json`.
2. On Analytics page, next to each headline number (ROI, drift p95, edge threshold), show Δ in small text:  
   `ROI: 1.8% ↑ +0.4pp since last refresh`.

### Tests
- `tests/test_polymarket_analytics.py::test_delta_shows_when_prev_present` — craft both jsons in a tmp dir.
- `tests/test_polymarket_analytics.py::test_no_delta_when_prev_missing` — confirm graceful absence.

### Acceptance
- When `analytics.prev.json` is present, Δ values show.
- When absent, page renders without errors.

---

## 8. Cross-cutting constraints

- **Do not change** `POLYMARKET_SECTIONS`, sidebar grouping, or `/polymarket/*` URLs.
- **Do not introduce** new JS libraries. Vanilla JS + Tailwind + inline SVG only.
- **A11y**: all new interactive elements need `aria-*` + focus styles matching the existing sidebar link style (`focus-visible:ring-...`).
- **Dark mode**: every new class pair must include both `light-*` and `dark-*` variants.
- **No breaking changes** to JSON endpoints (`/polymarket/freshness`, `/polymarket/health`, `/polymarket/scorecard?format=json`).

---

## 9. Suggested commit sequence

1. `feat(polymarket): shared page header partial for secondary tabs`
2. `feat(polymarket): AI pages TL;DR + sample size + tooltips`
3. `feat(polymarket): AI Performance recent-blocked drawer + helper`
4. `feat(polymarket): risky two-section layout + summary strip`
5. `feat(polymarket): risky empty-state CTA + interesting toggle`
6. `feat(polymarket): loss lab biggest-driver cards + sparkline`
7. `feat(polymarket): loss lab filter chips + explainers`
8. `feat(polymarket): analytics hero insights + svg bars + section badges`
9. `feat(polymarket): analytics delta vs previous export (requires polymarket-alerts change)`

Each commit message should include `CHANGELOG.md` entry under `[1.7.x]`.

---

## 10. Out of scope (do NOT do)

- Do not change Mirrors (`mirror_portfolio`, `mirror_alerts`) in any way.
- Do not rename routes or endpoints.
- Do not integrate DuckDB here — that belongs to `docs/DUCKDB_MIGRATION_PLAN.md`.
- Do not add a new top-level tab.
- Do not persist user preferences beyond existing `session` + `localStorage` patterns.

---

## 11. Definition of done

For each task:

- [ ] Implementation matches the spec above.
- [ ] New/edited templates render without template errors (`TemplateSyntaxError`, `UndefinedError`) in tests.
- [ ] `pytest -q` is green.
- [ ] Accessibility pass (keyboard tab order, focus rings, color contrast in dark mode).
- [ ] `CHANGELOG.md` entry added.
- [ ] Manual smoke: navigate Live → Tools overview → each migrated page; no stuck filters or broken anchors.
- [ ] Service restarted on the target host; browser hard-refreshed.

---

## 12. References

- Existing templates: `app/templates/polymarket_*.html`.
- Existing helpers: `app/utils/polymarket.py` (`get_strategy_scorecard`, `get_ai_performance`, `get_risky_historical_performance`, `get_loss_breakdown*`, `get_analytics_json`, `get_recent_decisions`).
- Sidebar + header layout: `app/templates/base.html` (`sidebar-row-heading`, `nav-label`, `is-collapsed` conventions).
- Freshness strip: `app/templates/polymarket_freshness_strip.html`.
- Color tokens: `tailwind.config` in `app/templates/base.html` — use `status-up-*`, `status-down-*`, `status-degraded-*` for TL;DR semantics.
- Tests fixture: `tests/fixtures/alerts_log_header.json`.
