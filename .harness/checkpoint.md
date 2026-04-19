# Harness Checkpoint

## Last Completed
**unit_024 (PHASE_005):** `sync_harness.py` now reports three fleet-drift divergence types so `/sync` and `/state` can surface broken batches.

- **New private helpers** in [sync_harness.py](skills/development-harness/scripts/sync_harness.py):
  - `_list_on_disk_worktrees(root)` — scans `.harness/worktrees/<batch>/<unit>/` and yields `(batch_id, unit_id, relpath)` triples.
  - `_list_harness_branches(root)` — shells to `git branch --list --format=%(refname:short)` and filters for `harness/batch_*/<unit>` names. Silently returns `[]` when git is unavailable — sync is informational, not critical.
  - `_detect_fleet_drift(root, state)` — cross-references `state.execution.fleet.units` against the on-disk worktrees and git branches.
- **New divergence types** (appended to the existing `divergences` array):
  1. **`orphan_worktree`** — `{type, worktree_path, batch_id, unit_id}` for on-disk directories not in fleet.
  2. **`stale_fleet_entry`** — `{type, unit_id, worktree_path, branch, batch_id}` for fleet entries whose `worktree_path` is missing on disk.
  3. **`orphan_branch`** — `{type, branch, batch_id, unit_id}` for `harness/batch_*/<unit>` branches without a matching fleet entry.
- Each divergence carries the `batch_id` + `unit_id` needed to feed into `teardown_batch --batch-id <id>` or a re-dispatch. `run_sync()` now loads `state.json` (optional) alongside the existing `phase-graph.json` / `config.json` pair.

**Test coverage:** 5 new `TestFleetDriftDetection` cases in [test_sync_harness.py](skills/development-harness/scripts/tests/test_sync_harness.py) plus 3 pre-existing `TestSyncHarness` cases — 8/8 green. Helpers `_init_git_repo`, `_write_state_with_fleet`, `_minimal_phase_graph` keep the new test class lean. Cases cover: on-disk worktree without fleet entry → orphan; fleet entry without worktree → stale; git branch without fleet entry → orphan; clean state → zero fleet-drift divergences; one-of-each combined case reported separately via a by-type dict.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_025 (PHASE_005):** New [skills/development-harness/scripts/tests/integration/test_parallel_invoke.py](skills/development-harness/scripts/tests/integration/test_parallel_invoke.py) — builds a fixture git repo, sets up a 3-unit phase, runs `dispatch_batch.py` then shell-scripted **fake agents** that commit canned files in each worktree, then `merge_batch.py`. Asserts final state, clean worktree removal, and no residual `harness/batch_*/` branches. **This is the PHASE_005 closing unit.** After it merges, open the PR, dispatch `code-review`, autonomous squash-merge per [harness-git.md](.claude/rules/harness-git.md).

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/sync_harness.py](skills/development-harness/scripts/sync_harness.py): added `_list_on_disk_worktrees`, `_list_harness_branches`, `_detect_fleet_drift`; `run_sync()` now reads state.json and appends fleet-drift divergences.
- [skills/development-harness/scripts/tests/test_sync_harness.py](skills/development-harness/scripts/tests/test_sync_harness.py): new `TestFleetDriftDetection` class with 5 cases, plus helpers.
- `python -m py_compile skills/development-harness/scripts/sync_harness.py` exits 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.test_sync_harness -v` passes 8/8 (2.1s).
- `python -m unittest discover skills/development-harness/scripts/tests` passes **169/169** (up from 164 at end of unit_023) in 35.3s.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; this session continues under `/loop /invoke-development-harness`. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_005 PR opens after unit_025 (the next unit closes the phase).
- **Branch:** `feat/phase-005-worktree-dispatch`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 24 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_005 progress: **6/7 units done** (019 dispatch, 020 merge, 021 teardown, 022 scope-violation, 023 lock mutex, 024 sync drift). Remaining: 025 integration test `test_parallel_invoke.py`.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → **169** across phases so far.

---
*Updated: 2026-04-20T02:35:00Z*
