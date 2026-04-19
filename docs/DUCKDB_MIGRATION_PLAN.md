# DuckDB Integration Plan (MiniStatus)

> Status: **planning reference** — not yet implemented.
> Scope: add **DuckDB** as an optional analytics query engine on top of the existing CSV/JSON artifacts written by **polymarket-alerts**.
> Goal: faster Loss Lab / Analytics / Scorecard without giving up the CSV source of truth, and without running a DB server.

---

## 0. Decisions captured before we start

| Decision | Choice | Rationale |
|---|---|---|
| Engine | **DuckDB** (embedded, columnar) | Workload is OLAP aggregations; reads CSV/Parquet in place; no server |
| Source of truth | **CSV/JSON** from `POLYMARKET_DATA_PATH` stays authoritative | polymarket-alerts is the writer; no forced schema migration |
| Writer | **None** inside MiniStatus | MiniStatus remains read-only |
| Rollout | **Behind an env flag** (`MINISTATUS_USE_DUCKDB=1`), route-by-route | Easy to A/B against current code |
| Upgrade path | CSV → Parquet (optional, later) | Same queries; 5–10× faster reads; polymarket-alerts writes both |

Related docs: `docs/POLYMARKET_INTEGRATION.md`, `docs/MINISTATUS_INTEGRATION.md`, `CHANGELOG.md`.

---

## 1. Prerequisites & baseline (before any code)

1. Capture a **performance baseline** using the plan in our notes:
   - `time curl -s -o /dev/null -w '%{time_total}\n' http://HOST:PORT/polymarket/<route>` (cold & warm) for Live, Scorecard, AI Simulation, Analytics, Loss Lab, Risky.
   - `wc -l $POLYMARKET_DATA_PATH/alerts_log.csv`, `ls -lh $POLYMARKET_DATA_PATH/*.csv`.
   - Gunicorn worker RSS: `ps -o rss= -p <pid>` before/after walking every page.
   - Save results to `docs/perf/BASELINE_YYYY-MM-DD.md` (commit).
2. Confirm **retention policy** for `alerts_log.csv` (currently 90 days via `retention_alerts_log.py`). Note actual row count so we can size DuckDB tests.
3. Read this doc and **`docs/POLYMARKET_INTEGRATION.md` §Schemas**, so the engine module mirrors current column names.

Exit criterion for step 1: at least one page is slow enough to justify the change (> 1.5 s warm or > 4 s cold), or row counts are trending toward > 500 k.

---

## 2. Dependency & packaging

1. Add `duckdb>=0.10` to `requirements.txt`.
2. Regenerate `requirements-ci-minimal.txt` via `python scripts/sync_requirements_ci_minimal.py`.
3. Confirm wheels exist for our target Python / arch (`pip install --dry-run duckdb`).
4. Do **not** import duckdb at module import time in existing code. It must be a soft import in the new module so the app still runs with `MINISTATUS_USE_DUCKDB` off.

---

## 3. Minimal module layout

Create these files (do not modify existing routes yet):

```
app/utils/polymarket_duckdb.py     # connection, helpers, queries
tests/test_polymarket_duckdb.py    # query correctness & fallback
docs/perf/BASELINE_YYYY-MM-DD.md   # baseline from step 1
docs/perf/DUCKDB_YYYY-MM-DD.md     # after cut-over
```

### 3.1 `polymarket_duckdb.py` contract

Public API (first draft):

```python
def duckdb_available() -> bool: ...
def is_enabled() -> bool:  # reads MINISTATUS_USE_DUCKDB env var
    ...

def get_connection() -> "duckdb.DuckDBPyConnection":
    """Cached per-process, in-memory, read-only. Safe to call from Flask workers."""

def scorecard_rows(data_path: str, *, safe_scope: str, days: int | None,
                   strategy: str | None) -> list[dict]:
    """Same return shape as get_strategy_scorecard() in polymarket.py."""

def loss_lab_rows(...): ...
def analytics_edge_buckets(...): ...
```

Rules:

- Each helper takes `data_path` and builds the path to CSV inside the function (`os.path.join(data_path, "alerts_log.csv")`).
- Use `read_csv_auto('...', header=true, sample_size=-1, all_varchar=false)` with an **explicit column spec** pulled from `ALERTS_HEADER` (keep a copy in `app/utils/polymarket_constants.py`).
- **No persistent DB file** in v1. Use `:memory:`; DuckDB scans CSV on demand. Cache at the **Python** level by file mtime (mirror `_CSV_CACHE` logic in `app/utils/polymarket.py`).
- On any exception, **raise** — the caller should fall back to the existing CSV path.

### 3.2 Fallback pattern (important)

Wrap the first migrated route like:

```python
if duckdb_available() and is_enabled():
    try:
        rows = polymarket_duckdb.scorecard_rows(...)
    except Exception as e:
        current_app.logger.warning("duckdb scorecard failed: %s; falling back", e)
        rows = get_strategy_scorecard(...)
else:
    rows = get_strategy_scorecard(...)
```

Keep fallback for at least one full release cycle.

---

## 4. First migration target: Scorecard

Chosen because it has an existing pure function (`get_strategy_scorecard`), clear return shape, and a dedicated test file.

Steps:

1. **Draft SQL** that reproduces the Python logic:
   ```sql
   WITH sent AS (
     SELECT * FROM read_csv_auto($csv)
     WHERE status = 'sent'
       AND ( $strategy IS NULL OR strategy_id = $strategy )
       AND ( $safe_only = FALSE OR sport IN ($allowlist) )
   ),
   resolved AS (
     SELECT * FROM sent
     WHERE resolved = 'true'
       AND TRY_CAST(pnl_usd AS DOUBLE) IS NOT NULL
       AND ( $days IS NULL OR resolved_ts >= CURRENT_TIMESTAMP - INTERVAL ($days) DAY )
   )
   SELECT strategy_id,
          COUNT(*)                                AS resolved,
          SUM(CASE WHEN CAST(pnl_usd AS DOUBLE) > 0 THEN 1 ELSE 0 END) AS wins,
          SUM(CASE WHEN CAST(pnl_usd AS DOUBLE) < 0 THEN 1 ELSE 0 END) AS losses,
          SUM(CAST(pnl_usd AS DOUBLE))            AS total_pnl
   FROM resolved
   GROUP BY strategy_id
   ORDER BY strategy_id;
   ```
2. **Parity test** — `tests/test_polymarket_duckdb.py::test_scorecard_matches_python`:
   - Build a fixture CSV with known rows (extend existing canonical-header fixture).
   - Run both `get_strategy_scorecard()` and `polymarket_duckdb.scorecard_rows()`; assert equal sets (order-independent by `strategy_id`).
3. **Route wiring** in `polymarket_scorecard` with the fallback pattern from §3.2.
4. **Manual benchmark**: record cold/warm timings on the slowest strategy filter; compare to baseline.
5. **Flip the flag**: set `MINISTATUS_USE_DUCKDB=1` in the service env (`systemctl edit ministatus` → `Environment=...`) and restart.

Exit criterion: Scorecard faster (or at worst equal) + parity test green.

---

## 5. Subsequent migrations

Do each as a separate PR / commit. Migrate in this order (highest payoff first):

1. **Loss Lab** (`get_loss_breakdown*`): heavy group-by over resolved losing rows.
2. **Analytics edge/timing buckets** that are currently recomputed in Python when the JSON is stale.
3. **Risky historical performance**: similar group-by.
4. **Open Positions stats** where we scan `alerts_log.csv` to derive bankroll/exposure numbers.

Each migration = SQL draft + parity test + fallback wiring + benchmark note.

---

## 6. (Optional) Parquet snapshot

After at least three routes are on DuckDB, consider adding a Parquet snapshot for `alerts_log`.

1. In **polymarket-alerts**, add a nightly job (or hook into `analytics_export.py`) that writes `alerts_log.parquet` next to the CSV.
2. In MiniStatus, DuckDB helper prefers Parquet when present:
   ```python
   path = os.path.join(data_path, "alerts_log.parquet")
   if not os.path.isfile(path):
       path = os.path.join(data_path, "alerts_log.csv")
   ```
3. Benchmark again; update `docs/perf/…`.

No query changes required — same SQL reads either format.

---

## 7. Caching & invalidation

- **Per-file mtime cache** keyed by `(abs_path, mtime)` → last result. Mirror the logic in `_read_csv_cached`.
- **Connection**: one DuckDB in-memory connection **per worker process**, lazily created. Do not share across processes.
- **Query results**: cache at the Python layer (small `lru_cache` or mtime dict). DuckDB itself is stateless here.
- **Cache bust** happens automatically when the CSV mtime changes.

Document the policy in `app/utils/polymarket_duckdb.py` module docstring.

---

## 8. Observability

1. Add a log line per query: `duckdb scorecard rows=<n> took=<ms>` at `DEBUG`.
2. Extend `/polymarket/health` JSON with:
   ```json
   "duckdb": { "enabled": true, "version": "0.10.1" }
   ```
3. Add a small `scripts/perf_probe.py` that hits key routes N times and prints p50/p95. Commit baseline + post-DuckDB runs to `docs/perf/`.

---

## 9. Tests (ordered)

1. **Availability**: `tests/test_polymarket_duckdb.py::test_duckdb_available` — skipped if not installed.
2. **Parity**: one test per migrated helper (see §4.2).
3. **Fallback**: monkey-patch `duckdb_available` to `False` and confirm the route still renders.
4. **Feature flag**: unset `MINISTATUS_USE_DUCKDB` → Python path used; set → DuckDB path used.
5. **Header-change guard**: after any change to `ALERTS_HEADER`, re-run `tests/test_polymarket_alerts_schema_fixture.py` and the DuckDB parity tests.

All tests must pass in both CI matrices (full + minimal). Minimal CI should `pip install duckdb` only if the flag is on — otherwise rely on the soft-import skip.

---

## 10. Rollout & rollback

1. Land code **with flag off** and fallback wired.
2. Deploy to the server; restart service.
3. Enable flag in service env; restart; observe a full day of traffic.
4. Compare perf snapshots (`docs/perf/DUCKDB_*.md` vs baseline).
5. If regressions: unset the env var, restart — fallback takes over. No code revert needed.
6. After two weeks stable, consider removing the fallback path for migrated routes (separate commit).

---

## 11. What we intentionally do **not** do (v1)

- No MiniStatus-side writes.
- No persistent `.duckdb` file (in-memory only).
- No schema divergence from `ALERTS_HEADER` — DuckDB reads the CSV shape as-is.
- No switch to Postgres; revisit only if multi-machine or multi-writer requirements appear.
- No removal of `_CSV_CACHE` / CSV helpers — they remain as the fallback code path.

---

## 12. Checklist (copy into a PR description)

- [ ] Baseline captured in `docs/perf/BASELINE_*.md`
- [ ] `duckdb` added to `requirements.txt` and CI-minimal sync run
- [ ] `app/utils/polymarket_duckdb.py` with soft import + `is_enabled()`
- [ ] Parity tests for first migrated helper (Scorecard)
- [ ] Fallback wired in route; feature flag documented in README
- [ ] `/polymarket/health` reports DuckDB status
- [ ] Post-migration perf numbers in `docs/perf/DUCKDB_*.md`
- [ ] `CHANGELOG.md` entry under the next version

---

## 13. References

- DuckDB docs: <https://duckdb.org/docs/>
- DuckDB Python API: <https://duckdb.org/docs/api/python/overview>
- `read_csv_auto`: <https://duckdb.org/docs/data/csv/overview>
- Existing consumers to migrate: `app/utils/polymarket.py` (`get_strategy_scorecard`, `get_loss_breakdown*`, `get_risky_historical_performance`, etc.).
- Schema fixture: `tests/fixtures/alerts_log_header.json` and producer copy in `polymarket-alerts/docs/alerts_log_header.json`.
