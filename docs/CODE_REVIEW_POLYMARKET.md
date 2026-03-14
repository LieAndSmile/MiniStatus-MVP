# Code review: Polymarket tabs (duplicates, dead code, strategy preservation)

## Summary

- **Dead code:** ~~`get_expectancy_by_bands()` and its band constants~~ **FIXED** – Removed from `app/utils/polymarket.py`.
- **Stale docs:** ~~README and polymarket-alerts docs still mention the Performance tab~~ **FIXED** – MiniStatus README and polymarket-alerts docs updated.
- **Strategy reset bug:** ~~Portfolio, Open Positions, Risky, and Loss Lab do not pass `strategy=current_strategy`~~ **FIXED** – All tabs now preserve strategy in filter/sort/time-window links.
- **No other duplicate tabs:** Analytics is the single analytics view; Loss Lab is distinct; Risky is a filtered view of Open Positions (intentional).

---

## 1. Dead code

| Location | Item | Action |
|----------|------|--------|
| `app/utils/polymarket.py` | `get_expectancy_by_bands()`, `_EDGE_BANDS`, `_GAMMA_BANDS` | Only used by the removed Performance tab. Remove to avoid dead code. |

---

## 2. Stale documentation

| Location | Issue |
|----------|--------|
| **MiniStatus** `README.md` | Table row "**Performance** \| `/polymarket/performance` \| ..." still present. Risky row says "Results ... appear in **Performance**" → should say **Analytics**. "Time window" bullet still lists "Portfolio, Performance, Loss Lab". |
| **polymarket-alerts** `docs/MINISTATUS_INTEGRATION.md` | "Used on Portfolio, Open Positions, Risky, **Performance**, Loss Lab, Loop, Analytics, and Lifecycle" and "Portfolio, Open Positions, Risky, **Performance**, Loss Lab, Loop" — remove Performance. |
| **polymarket-alerts** `docs/README.md` | Tab list includes "Performance" — remove. |

---

## 3. Strategy not preserved (same bug as Loop/Dev)

When the user changes **Time window**, **Sort**, **Category**, or other filters on these tabs, the Strategy dropdown resets to "safe" because the generated links omit the `strategy` query parameter.

| Tab | File | Fix |
|-----|------|-----|
| **Portfolio** | `polymarket.html` | Add `strategy=current_strategy` to every `url_for('polymarket.polymarket_portfolio', ...)` (filter, sort, time, category, pagination, export). |
| **Open Positions** | `polymarket_positions.html` | Add `strategy=current_strategy` to `positions_extra` / `positions_extra_no_from` and to every filter/sort link and the time filter extra. Add hidden `strategy` to the refresh form so redirect keeps it. |
| **Risky** | `polymarket_risky.html` | Add `strategy=current_strategy` to `risky_extra_no_from` and to every `url_for('polymarket.polymarket_risky', ...)` (time filter, sort options, clear from-date). |
| **Loss Lab** | `polymarket_loss_lab.html` | Pass `{'strategy': current_strategy}` as extra to `polymarket_time_filter()`. Add strategy to the "View in Portfolio" link. |

---

## 4. Duplicates / overlap

- **Performance vs Analytics:** Removed. Analytics (Edge Quality, Timing, Strategy Cohort, MTM/Exit Study) is the single analytics view.
- **Risky vs Open Positions:** Not a duplicate. Risky is a filtered subset of the same data (high edge, low gamma, short expiry); both are needed.
- **Portfolio vs Analytics:** Portfolio = resolved list + KPIs + charts from CSV. Analytics = pre-aggregated buckets and strategy cohort from `analytics.json`. Different data and purpose; no duplication.

---

## 5. Other

- **Sidebar vs horizontal tabs:** Both are driven by `POLYMARKET_SECTIONS` and base.html sidebar; they stay in sync. No duplicate definitions.
- **Export / Refresh:** Portfolio export and positions refresh correctly preserve params via form or redirect; adding strategy to links keeps strategy in the URL for all tabs.
