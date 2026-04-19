# Harness Checkpoint

## Last Completed
**PHASE_005 complete (all 7 units).** The worktree-per-unit parallel execution substrate is now fully implemented and test-covered.

- **unit_019** — [dispatch_batch.py](skills/development-harness/scripts/dispatch_batch.py): per-unit `git worktree add -b harness/<batch_id>/<unit_id>` + `WORKTREE_UNIT.json` seed + `state.execution.fleet` writes; atomic `_rollback` on any per-unit failure.
- **unit_020** — [merge_batch.py](skills/development-harness/scripts/merge_batch.py): serial `git merge --no-ff` fan-in with `abort_batch` / `serialize_conflicted` strategies; post-merge validator hook with `git reset --hard <pre_merge_ref>` rollback on failure; cleanup of merged units' worktrees + branches.
- **unit_021** — [teardown_batch.py](skills/development-harness/scripts/teardown_batch.py): idempotent scoped / global cleanup of harness batch worktrees + branches; tolerates every missing-state case.
- **unit_022** — scope-violation detector in `merge_batch.py` (three helpers `_is_within_scope`, `_scope_violations`, `_read_worktree_touches_paths`): every unit's diff is checked against its declared `touches_paths` before merge; violators get `conflict.category="scope_violation"` and are hard-rejected regardless of `conflict_strategy`.
- **unit_023** — `_MergeLock` `O_EXCL` mutex on `.harness/.lock` wraps `merge_batch()`; blocking acquire with configurable timeout / stale-after / poll interval; exception-path release; `MergeError` when fresh lock holds past `lock_timeout`.
- **unit_024** — `sync_harness.py` now reports three fleet-drift divergence types (`orphan_worktree`, `stale_fleet_entry`, `orphan_branch`), each carrying `batch_id` + `unit_id` for downstream cleanup wiring.
- **unit_025** — new [tests/integration/test_parallel_invoke.py](skills/development-harness/scripts/tests/integration/test_parallel_invoke.py) exercises the full pipeline end-to-end: dispatch → fake agents committing canned files in each worktree → `merge_batch` → assertions on final fleet state, files-on-main, merge-commit messages, and cleanup (no residual worktrees, no residual branches). Added a `_prune_empty_dir` helper to `merge_batch.py` so the `.harness/worktrees/<batch_id>/` parent dir is removed when the whole batch resolves.

**Test-suite growth across the phase:** 134 → 144 → 160 → 164 → 169 → **171** (+37 cases in PHASE_005 alone). Three new scripts (`dispatch_batch.py`, `merge_batch.py`, `teardown_batch.py`), one extended (`sync_harness.py`), one new integration package.

## What Failed (if anything)
On the first run of the integration test, the happy-path assertion "no residual worktrees" failed because `merge_batch` left the now-empty `.harness/worktrees/<batch_id>/` parent directory behind. Fixed by adding a `_prune_empty_dir` helper that matches the pattern already in `teardown_batch.py`. Re-run: both integration cases pass, and no existing `test_merge_batch` case regresses.

## What Is Next
**Run PHASE_005 phase completion review**, open the phase PR, autonomous squash-merge per [harness-git.md](.claude/rules/harness-git.md). After merge, advance to **unit_026 (PHASE_006, orchestrator-agent-contract)** — a new `templates/claude-code/agents/harness-unit.md` with system prompt, tool allowlist (no `git push`, no writes to `.harness/`, no writes outside the worktree), and the required JSON report schema.

## Blocked By
None.

## Evidence
- 3 new scripts + 1 extended: `dispatch_batch.py` (207 LOC), `merge_batch.py` (363 LOC after unit_023 + unit_024), `teardown_batch.py` (146 LOC), extended `sync_harness.py`.
- 5 new test modules + 1 extended: `test_dispatch_batch.py` (9 cases), `test_merge_batch.py` (16 unit_020 + 4 unit_023 = 20 cases), `test_teardown_batch.py` (10 cases), `test_scope_violation.py` (16 cases), extended `test_sync_harness.py` (+5 cases = 8 total), new integration `test_parallel_invoke.py` (2 cases).
- `python -m py_compile` on every new/changed file exits 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.integration.test_parallel_invoke -v` passes 2/2 (2.9s).
- `python -m unittest discover skills/development-harness/scripts/tests` passes **171/171** in 36.1s.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; this session continues under `/loop /invoke-development-harness`. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_005 PR opens now with all seven units.
- **Branch:** `feat/phase-005-worktree-dispatch` (delete on merge).
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 25 / `loop_budget` 12 — `/loop` remains the driver; 13 units have now been completed end-to-end under `/loop`-driven continuation this session (unit_014 through unit_025 plus the ISSUE_002 injection turn).
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → **171** across phases so far.

---
*Updated: 2026-04-20T03:00:00Z*
