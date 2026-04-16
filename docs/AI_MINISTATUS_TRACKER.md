# AI ↔ MiniStatus integration — status notes

**Canonical copy (keep in sync when you change milestones):**  
`polymarket-alerts/docs/AI_MINISTATUS_TRACKER.md`

**How MiniStatus uses producer data:** `docs/MINISTATUS_INTEGRATION.md`  
**Producer contract:** `polymarket-alerts/docs/INTEGRATION_CONTRACT.md`

---

## Done (summary)

- **Phase 1–4:** through **`last_screen_meta`** (reason codes, summary, model, prompt version) in loop state + export + MiniStatus diagnostics; LLM schema extended accordingly on the producer.
- **Nothing mandatory left** for this track; remaining items are ops and future schema bumps.

## Quick reminders

- After producer deploy: `systemctl daemon-reload`; analytics timer should refresh **`ai_performance.json`** with **`analytics.json`**.
- **Stale export gate:** `scripts/check_file_freshness.py` can fail on old `ai_performance.json` when that file exists — disable with **`FILE_FRESHNESS_CHECK_AI_PERFORMANCE=0`** if needed.
- Before releases: `pytest` in **both** repos; bump MiniStatus **`AI_ARTIFACT_SCHEMA_VERSION`** if producer **`schema_version`** changes.

For the full checklist and table, open the **canonical** tracker in **polymarket-alerts** (path above).
