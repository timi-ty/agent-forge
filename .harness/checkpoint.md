# Harness Checkpoint

## Last Completed
**unit_021 (PHASE_005):** Idempotent batch teardown landed. PHASE_005 now has dispatch + merge + teardown — the three repo-side primitives.

- **Public API:** `teardown_batch(root, batch_id=None)` in [skills/development-harness/scripts/teardown_batch.py](skills/development-harness/scripts/teardown_batch.py). Returns `{removed_worktrees, deleted_branches, batch_ids}` listing what **this invocation** removed (so a second call on the same batch correctly reports empty lists).
- **Two modes:**
  - Scoped: `batch_id="<id>"` — used by error-recovery paths after a specific dispatch went sideways.
  - Global: `batch_id=None` — used by `/clear` to blank-slate every batch directory and every `harness/batch_*/` branch.
- **Graceful missing-state handling:** every git invocation uses `check=False`. Branches can exist without on-disk worktrees (an orphan from a previous crash) and vice-versa; both are cleaned up. Orphaned on-disk worktree directories that `git worktree remove --force` can't process are scrubbed with `shutil.rmtree`. Final `git worktree prune` resyncs git's internal metadata.
- **CLI:** `--batch-id` (default: all) `--root` (default: `find_harness_root()`). Prints the summary JSON to stdout.

**Test coverage:** 10 new cases across 4 classes in [test_teardown_batch.py](skills/development-harness/scripts/tests/test_teardown_batch.py).
- `TestScopedTeardown` (4) — single-batch teardown; second run is a no-op (the idempotence property); scoped teardown leaves other batches alone; phantom batch_id is a no-op.
- `TestGlobalTeardown` (2) — every batch and every harness branch removed in one pass; clean-repo global teardown is a no-op.
- `TestMissingStateTolerance` (2) — orphaned branch without worktree still gets deleted; orphaned on-disk worktree dir without a branch still gets scrubbed.
- `TestCliSmoke` (2) — `--help` and end-to-end scoped teardown via the CLI binary.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_022 (PHASE_005):** Scope-violation detector in `merge_batch.py`. Before each unit's `git merge --no-ff`, run `git diff --name-only <merge-base>..<branch>` and reject any unit whose diff includes files matching **none** of the unit's declared `touches_paths` globs. The sub-agent self-report is never trusted for blast radius — the diff is the source of truth. Rejected units are marked `status="failed"` with `conflict.category="scope_violation"` (new category alongside the existing merge-conflict categories). Test: `python -m unittest skills.development-harness.scripts.tests.test_scope_violation`.

**Implementation note for next turn:** the scope check is a new helper that takes `(root, branch, touches_paths) -> (violations: list[str])` and is called from `merge_batch.py` inside the per-unit loop, immediately before `_merge_unit`. The existing `_patterns_overlap` helper in `compute_parallel_batch.py` is the right matcher — reuse it rather than re-implementing glob matching.

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/teardown_batch.py](skills/development-harness/scripts/teardown_batch.py): new 146-line module.
- [skills/development-harness/scripts/tests/test_teardown_batch.py](skills/development-harness/scripts/tests/test_teardown_batch.py): new 172-line test module, 10 cases.
- `python -m py_compile` on both new files exits 0 (0.15s).
- `python -m unittest skills.development-harness.scripts.tests.test_teardown_batch -v` passes 10/10 (4.4s).
- `python -m unittest discover skills/development-harness/scripts/tests` passes **144/144** (up from 134 at end of unit_020) in 27.8s.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; this session continues under `/loop /invoke-development-harness`. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_005 PR opens after unit_025.
- **Branch:** `feat/phase-005-worktree-dispatch`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 21 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_005 progress: **3/7 units done** (019 dispatch, 020 merge, 021 teardown). Remaining: 022 scope-violation detector, 023 .harness/.lock mutex, 024 sync_harness orphan detection, 025 integration test.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → **144** across phases so far.

---
*Updated: 2026-04-20T01:25:00Z*
