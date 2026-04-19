# Harness Checkpoint

## Last Completed
**unit_042 (PHASE_010):** `/harness-state` docs now render fleet + orphans + per-batch timings.

Both [commands/state.md](skills/development-harness/commands/state.md) and the workspace-commands mirror [templates/workspace-commands/harness-state.md](skills/development-harness/templates/workspace-commands/harness-state.md) gained three new output sections plus the procedural steps that populate them:

- **Fleet & Batch** — reads `state.execution.fleet.mode`, `.batch_id`, `.units[]`; reuses the per-unit table columns from unit_041's checkpoint-template Batch section so consumers can cross-reference.
- **Orphans** — runs [sync_harness.py](skills/development-harness/scripts/sync_harness.py) (read-only reporter); renders the three divergence categories `orphan_worktree`, `stale_fleet_entry`, `orphan_branch`. When `divergences[]` is empty, the doc explicitly requires rendering `"No orphans detected."` — absence is a reported fact, not an omission.
- **Batch Timings** — sources from `.harness/logs/<batch_id>/` (to be created by unit_043); specifies the exact one-line format:
  ```
  Batch <batch_id>: dispatched HH:MM:SS, merged HH:MM:SS, total Ns
  ```
  Fallback when no logs: `"Batch timings: unavailable"`. Git-timestamp inference is **explicitly forbidden** — the logs are authoritative.

Two new **Honesty Rules** pin the never-omit behavior for Orphans and Batch Timings so an agent can't skip the section when empty/unavailable.

### New regression test
[test_harness_state_docs.py](skills/development-harness/scripts/tests/test_harness_state_docs.py) — 5 cases in `TestHarnessStateDocCoverage`:
1. Fleet & Batch heading present in both docs + `fleet.mode`/`fleet.batch_id`/`fleet.units` references.
2. Orphans heading + `sync_harness.py` mention + all three divergence categories + the empty-case "No orphans detected." render.
3. Batch Timings heading + exact timing-line format string + "Batch timings: unavailable" fallback.
4. `.harness/logs/` directory layout reference present (so the agent knows where to look once unit_043 lands).
5. Explicit git-timestamp-inference ban present in both docs.

### Grounding
`sync_harness.py` is read-only (always a reporter, never a mutator). The phase doc's "sync_harness.py --dry-run" phrasing is simplified to plain `sync_harness.py` in both command docs to match actual script behavior. The three divergence categories are the exact set emitted at [sync_harness.py:211–255](skills/development-harness/scripts/sync_harness.py#L211-L255).

## What Failed (if anything)
None.

## What Is Next
**Complete unit_043 (PHASE_010):** implement log-directory creation logic.

- `dispatch_batch.py` — create `.harness/logs/<batch_id>/batch.json` at dispatch time with the full batch plan + overlap analysis.
- `merge_batch.py` — write `merge.log` (merge output) and `validation.log` (post-merge validation output) under `.harness/logs/<batch_id>/`.
- Sub-agent `<unit_id>.md` summaries are written by sub-agents per the harness-unit contract — confirm the path, no orchestrator code needed.
- Logs must be harness-owned and gitignored — add `.harness/logs/` to `.gitignore` if not already present.
- Wrap all log writes in `try/except` so merge is not blocked by log-dir issues (per phase doc rollback guidance).
- New `test_batch_logs.py` asserts dispatch + merge produce the expected artifacts in a temp-dir fixture.

## Blocked By
None.

## Evidence
- [skills/development-harness/commands/state.md](skills/development-harness/commands/state.md): three new procedural steps (2b, 2c) + three new Output Report sections (Fleet & Batch, Orphans, Batch Timings) + two new Honesty Rules.
- [skills/development-harness/templates/workspace-commands/harness-state.md](skills/development-harness/templates/workspace-commands/harness-state.md): mirror edits.
- [skills/development-harness/scripts/tests/test_harness_state_docs.py](skills/development-harness/scripts/tests/test_harness_state_docs.py): new 120-line test module, 5 cases.
- `python -m py_compile` → 0 (~0.1s) on new test file.
- `python -m unittest skills.development-harness.scripts.tests.test_harness_state_docs -v` → **5/5** in 0.002s.
- `python -m unittest discover skills/development-harness/scripts/tests` → **215/215** (up from 210) in 33.5s.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_010 PR opens after unit_044 (closes the phase).
- **Branch:** `feat/phase-010-observability`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 40 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_010 progress: **2/4 units done** (041 checkpoint Batch section, 042 `/harness-state` renderer). Remaining: 043 log-directory creation in dispatch/merge, 044 integration assertions.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → 206 → 210 → **215** across phases so far.

## Batch (current or last)

Reflects `state.execution.fleet`. When `mode == "idle"` and no batch has run yet, render `Batch ID: none`, `Mode: idle`, empty unit table, and "No conflicts." under Conflicts.

- **Batch ID:** none
- **Mode:** idle

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|

### Conflicts
No conflicts.

---
*Updated: 2026-04-20T08:15:00Z*
