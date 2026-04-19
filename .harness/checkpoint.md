# Harness Checkpoint

## Last Completed
**unit_041 (PHASE_010):** Extended [checkpoint-template.md](skills/development-harness/templates/checkpoint-template.md) with a Batch section that reflects `state.execution.fleet`.

- **Four new placeholders:** `{{BATCH_ID_OR_NONE}}`, `{{FLEET_MODE}}`, `{{BATCH_UNIT_ROWS_OR_NONE}}`, `{{BATCH_CONFLICTS_OR_NONE}}`.
- **Per-unit table columns:** Unit, Phase, Status, Branch, Started, Ended — matches the fields already on `state.execution.fleet.units` (dispatch/merge state shape from PHASE_005), so the agent/script filling the template doesn't need to reshape data.
- **Guidance paragraph** documents the idle-with-no-prior-batch render: `Batch ID: none`, `Mode: idle`, empty unit table, `No conflicts.`
- **Grounding:** grep confirms no runtime script programmatically substitutes these placeholders. The template is seed material for [commands/create.md](skills/development-harness/commands/create.md)'s initial-checkpoint step. The additive edit is safe.

### New regression test
`TestCheckpointTemplateBatchSection` in [test_checkpoint_template.py](skills/development-harness/scripts/tests/test_checkpoint_template.py) (4 cases):
1. Heading `## Batch (current or last)` present.
2. All four new placeholders present.
3. Table header carries each of the 6 column names (trips if columns get shuffled or renamed).
4. All 7 pre-PHASE_010 placeholders survive the edit (guard against accidental deletion).

## What Failed (if anything)
None.

## What Is Next
**Complete unit_042 (PHASE_010):** update [commands/state.md](skills/development-harness/commands/state.md) and [templates/workspace-commands/harness-state.md](skills/development-harness/templates/workspace-commands/harness-state.md) to render three things:
1. Fleet status from `state.execution.fleet` (reuse the Batch section shape from unit_041).
2. Orphaned worktrees via `sync_harness.py --dry-run`.
3. Per-batch timings (dispatch start, merge complete, total wall-clock) — likely derived from `.harness/logs/<batch_id>/` once unit_043 lands, but unit_042 can at least specify the timing format (`Batch <id>: dispatched HH:MM:SS, merged HH:MM:SS, total Ns`).

Validation: grep both docs + structural presence test.

## Blocked By
None.

## Evidence
- [skills/development-harness/templates/checkpoint-template.md](skills/development-harness/templates/checkpoint-template.md): Batch section added.
- [skills/development-harness/scripts/tests/test_checkpoint_template.py](skills/development-harness/scripts/tests/test_checkpoint_template.py): new 90-line test module, 4 cases.
- `python -m py_compile` → 0 (~0.1s) on the new test file.
- `python -m unittest skills.development-harness.scripts.tests.test_checkpoint_template -v` → **4/4** in 0.001s.
- `python -m unittest discover skills/development-harness/scripts/tests` → **210/210** (up from 206) in 33.6s.

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
- `session_count` is 39 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_010 progress: **1/4 units done** (041 checkpoint Batch section). Remaining: 042 `/harness-state` renderer, 043 log-directory creation in dispatch/merge, 044 integration assertions.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → 206 → **210** across phases so far.

## Batch (current or last)

Reflects `state.execution.fleet`. When `mode == "idle"` and no batch has run yet, render `Batch ID: none`, `Mode: idle`, empty unit table, and "No conflicts." under Conflicts. Otherwise render the in-flight or most-recently-completed batch.

- **Batch ID:** none
- **Mode:** idle

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|

### Conflicts
No conflicts.

---
*Updated: 2026-04-20T07:50:00Z*
