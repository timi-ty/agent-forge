# Command: State

Read-only harness state report with alignment analysis.

## Mode

Read-only analysis. No modifications to any files.

## Steps

### 1. Validate Structural Health

Run `validate_harness.py` from `.harness/scripts/`:

```
$PY .harness/scripts/validate_harness.py
```

If validation fails, report errors prominently and continue with whatever data is readable.

### 2. Read Harness Data

Read all of these files:

- `.harness/state.json`
- `.harness/phase-graph.json`
- `.harness/config.json`
- `.harness/checkpoint.md`
- `.harness/ARCHITECTURE.md`
- All files in `PHASES/` directory

### 2b. Read Fleet & Batch State

Parse `state.execution.fleet` from `state.json`. This is the authoritative per-turn batch state. Extract:

- `fleet.mode` — one of `idle`, `dispatched`, `merging`.
- `fleet.batch_id` — the current (or most recent) batch identifier.
- `fleet.units[]` — per-unit records with `unit_id`, `phase_id`, `status`, `branch`, `started_at`, `ended_at`, `conflict`.

Then run the orphan-detector:

```
$PY .harness/scripts/sync_harness.py
```

`sync_harness.py` is read-only. Its `divergences[]` output surfaces three conditions:

- `orphan_worktree` — a directory under `.harness/worktrees/<batch>/<unit>/` exists on disk but has no matching `fleet.units` entry.
- `stale_fleet_entry` — a `fleet.units` entry references a `worktree_path` that no longer exists on disk.
- `orphan_branch` — a local git branch matching `harness/batch_*/*` exists without a corresponding on-disk worktree + fleet entry.

These indicate a crashed mid-batch turn. Recovery runs through `/sync-development-harness` + `teardown_batch.py`.

### 2c. Read Per-Batch Timings

If `.harness/logs/<batch_id>/` exists for the current or most recent `fleet.batch_id`, extract timings from the artifacts (introduced in unit_043):

- Dispatch start = earliest `started_at` among `fleet.units` (or `batch.json` timestamp).
- Merge complete = `ended_at` on the last-merged unit (or `merge.log` mtime).
- Total wall-clock = merge_complete − dispatch_start.

Render each batch timing as one line using this **exact** format so downstream tooling (and later `/sync`) can parse the report:

```
Batch <batch_id>: dispatched HH:MM:SS, merged HH:MM:SS, total Ns
```

If no `.harness/logs/` data exists yet (pre-unit_043 installs, or no parallel batch has run), render `Batch timings: unavailable` and note that this is expected on fresh installs.

### 3. Quick Checks (Optional)

Run these if the project supports them. Skip silently if not configured.

- `git status` — working tree cleanliness
- Test runner from `config.json` → `testing` section (e.g., `pnpm test`, `pytest`)
- Deployment smoke test from `config.json` → `deployment.smoke_test_url` (HTTP GET, check for 200)

Record which checks were run, which were skipped, and why.

### 4. Compute Alignment Metrics

Derive each metric from harness data. Show the calculation, not just the number.

| Metric | Derivation |
|--------|-----------|
| **Roadmap coverage** | Count ROADMAP.md sections that have a corresponding phase in `phase-graph.json`. Report as `N / M sections covered`. |
| **Phase coverage** | Phases with status `completed` / total phases. |
| **Unit coverage** | Units with status `completed` / total units across all phases. |
| **Test coverage** | Completed units that have non-empty `validation_evidence` / total completed units. |
| **Deploy coverage** | Deploy-verified phases (with Layer 6+ evidence) / total deploy-affecting phases. If no deploy-affecting phases exist, report N/A. |

### 5. Check Staleness

- Age of `state.json` — compare `last_updated` timestamp against current time
- Last sync — compare `drift.last_sync` against current time
- Checkpoint currency — compare `checkpoint.timestamp` against `state.json` `last_updated`

Flag anything older than 24 hours as potentially stale.

### 6. Output Report

Use this exact format:

```
# Harness State Report

## App State
(what exists in code, what works, what is broken — cite file paths and test output)

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
(each metric with how it was derived)

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

- Never pretend sync has happened if `drift.last_sync` has no value or is stale.
- Clearly separate known facts (direct data reads, test output) from inference (keyword matches, heuristic coverage).
- If percentages are reported, show the numerator and denominator (e.g., "3 / 7 units completed (43%)").
- If a quick check was skipped, say so. Do not fabricate results.
- If `state.json` or `phase-graph.json` is missing or corrupt, report the structural failure rather than guessing state.
- The **Orphans** section is never omitted. "No orphans detected." is a fact and must be rendered when `sync_harness.py` returns an empty `divergences[]`.
- The **Batch Timings** section is never omitted. If no timings exist, render `Batch timings: unavailable`. Do not infer timings from git timestamps — they are authoritative only when sourced from `.harness/logs/`.
