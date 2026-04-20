---
description: "Report full harness state with alignment analysis"
---

# Harness State

You are reporting the state of the development harness. This is read-only — do not modify any files.

## Procedure

1. Read `.harness/ARCHITECTURE.md` for file layout context.
2. Detect Python:
   ```bash
   PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
   [ -z "$PY" ] && { echo "Error: Python 3 is required but neither python3 nor python was found"; exit 1; }
   ```
3. Run: `$PY .harness/scripts/validate_harness.py`
   - If it fails, report errors and continue with readable data.
4. Read these files:
   - `.harness/state.json`
   - `.harness/phase-graph.json`
   - `.harness/config.json`
   - `.harness/checkpoint.md`
   - All `PHASES/*.md` files
5. **Read Fleet & Batch state.** Parse `state.execution.fleet` — `fleet.mode` (idle/dispatched/merging), `fleet.batch_id`, and `fleet.units[]` (each with `unit_id`, `phase_id`, `status`, `branch`, `started_at`, `ended_at`, `conflict`). Then run `$PY .harness/scripts/sync_harness.py` (read-only). Its `divergences[]` output surfaces three conditions: `orphan_worktree`, `stale_fleet_entry`, `orphan_branch`. These indicate a crashed mid-batch turn; recovery goes through `/sync-development-harness` + `teardown_batch.py`.
6. **Read per-batch timings** from `.harness/logs/<batch_id>/` for the current or most recent `fleet.batch_id` (introduced in unit_043). Render each batch timing using this **exact** format:
   ```
   Batch <batch_id>: dispatched HH:MM:SS, merged HH:MM:SS, total Ns
   ```
   If no `.harness/logs/` data exists yet (pre-unit_043 installs, or no parallel batch has run), render `Batch timings: unavailable`. Do not infer timings from git timestamps.
7. Run optional quick checks (skip silently if not configured):
   - `git status`
   - Test runner from `config.json` → `testing` (e.g., `pnpm test`)
   - HTTP GET to `config.json` → `deployment.smoke_test_url` if set
8. Compute alignment metrics from `phase-graph.json`:
   - **Phase coverage**: completed phases / total phases
   - **Unit coverage**: completed units / total units
   - **Test coverage**: completed units with `validation_evidence` / completed units
   - **Deploy coverage**: deploy-verified phases / deploy-affecting phases (N/A if none)
9. Check staleness: age of `state.json`, time since `drift.last_sync`, checkpoint currency.
10. Output this report:

```
# Harness State Report

## App State
(what exists, what works, what is broken — cite paths and output)

## Harness State
(active phase, progress, issue counts, last sync time)

## Fleet & Batch
(fleet.mode; fleet.batch_id; per-unit table with unit_id, phase_id, status, branch, started_at, ended_at; conflicts summary. Mirrors the Batch section of checkpoint-template.md — reuse the same column set so consumers can cross-reference.)

## Orphans
(divergences[] from sync_harness.py grouped by type: orphan_worktree, stale_fleet_entry, orphan_branch. If empty, render "No orphans detected." Never omit this section — absence is itself a reported fact.)

## Batch Timings
(one line per batch in `.harness/logs/`, most recent first, formatted exactly as:
`Batch <batch_id>: dispatched HH:MM:SS, merged HH:MM:SS, total Ns`.
If no timings are available, render "Batch timings: unavailable".)

## Alignment
(each metric with numerator/denominator, e.g. "3/7 units (43%)")

## Validation & Deployment Evidence
(last test run, last deploy status, CI status)

## Current Phase & Unit
(active phase, completed units, next unit)

## Blockers & Open Questions

## Risks

## Staleness
(age of state.json, time since last sync, checkpoint currency)

## Recommended Next Action
```

## Honesty Rules

- Never fabricate sync, test, or deploy results.
- Separate facts (data reads, test output) from inference.
- Show numerator and denominator for all percentages.
- If a check was skipped, say so.
- The **Orphans** section is never omitted. "No orphans detected." is a fact and must be rendered when `sync_harness.py` returns an empty `divergences[]`.
- The **Batch Timings** section is never omitted. If no timings exist, render `Batch timings: unavailable`. Do not infer timings from git timestamps — they are authoritative only when sourced from `.harness/logs/`.
