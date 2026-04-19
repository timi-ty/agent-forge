# Harness Checkpoint

## Last Completed
**unit_022 (PHASE_005):** Scope-violation detector now gates every merge. **The sub-agent's self-report is never trusted for blast radius — the diff is.**

- **New helpers in [merge_batch.py](skills/development-harness/scripts/merge_batch.py):**
  - `_is_within_scope(file_path, touches_paths)` — `fnmatch`-based, recursive-glob-aware (fnmatch's `*` naturally matches path separators, so `src/auth/**` covers descendants without extra translation).
  - `_scope_violations(root, branch, touches_paths)` — runs `git merge-base HEAD <branch>` then `git diff --name-only <merge-base>..<branch>`, returns the subset matching no declared glob.
  - `_read_worktree_touches_paths(root, worktree_path)` — reads the `touches_paths` list from the worktree's `.harness/WORKTREE_UNIT.json` (seeded by `dispatch_batch`). Returns `None` when the sentinel is missing, which causes the scope check to be skipped — we refuse to fabricate a scope from elsewhere.
- **Integration into the per-unit loop:** the scope check runs **before** `_merge_unit`. On violation, the unit is rejected with `status="failed"`, `conflict = {paths: <violators>, category: "scope_violation"}`. **No merge is attempted.** HEAD does not advance. The unit's branch is preserved for operator inspection.
- **Scope failures are always hard rejects** — they do not interact with `conflict_strategy`. A scope violation in unit A does **not** cause abort_batch to cascade into unit B. Well-scoped siblings still get their merge attempts.
- **Conflict-dict taxonomy:** added `category` to merge-conflict entries too (`"merge_conflict"`) alongside the existing `strategy_applied` field. Existing tests that assert on `strategy_applied` stay green; new consumers can query `category` uniformly.

**Test coverage:** 16 new cases across 4 classes in [test_scope_violation.py](skills/development-harness/scripts/tests/test_scope_violation.py).
- `TestIsWithinScope` (6) — literal match, recursive glob, non-recursive glob, non-match, empty scope rejects all, multi-glob any-match.
- `TestScopeViolationsHelper` (4) — in-scope branch returns `[]`; out-of-scope files returned verbatim; empty `touches_paths` flags every changed file; unknown branch yields `[]`.
- `TestReadWorktreeTouchesPaths` (3) — reads what `dispatch_batch` seeded; missing sentinel returns `None` (skip-check signal); empty list is preserved (not coerced to `None`).
- `TestMergeBatchRejectsScopeViolator` (3) — end-to-end: scope violator rejected before merge (HEAD pre/post SHA verified identical), branch preserved; well-scoped sibling merges alongside a scope violator with `outcome="partial"`; within-scope changes merge cleanly.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_023 (PHASE_005):** `.harness/.lock` file-based mutex around `merge_batch.py` using `O_EXCL`. Acquire the lock at `merge_batch()` entry; release at every exit (normal + exception paths). Second concurrent invocation must block until first releases. Document stale-lock detection (PID file contents + a very-old-mtime fallback). Acceptance: a contention test verifies serialization — two `merge_batch` calls run back-to-back even when scheduled concurrently.

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/merge_batch.py](skills/development-harness/scripts/merge_batch.py): added `_is_within_scope`, `_scope_violations`, `_read_worktree_touches_paths`; per-unit loop now scope-checks before merge.
- [skills/development-harness/scripts/tests/test_scope_violation.py](skills/development-harness/scripts/tests/test_scope_violation.py): new 276-line test module, 16 cases.
- `python -m py_compile` on edited module + new test file exits 0 (0.14s).
- `python -m unittest skills.development-harness.scripts.tests.test_scope_violation -v` passes 16/16 (4.0s).
- `python -m unittest discover skills/development-harness/scripts/tests` passes **160/160** (up from 144 at end of unit_021) in 27.8s. **Zero regressions in existing `test_merge_batch.py` despite the module-internal changes.**

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
- `session_count` is 22 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_005 progress: **4/7 units done** (019 dispatch, 020 merge, 021 teardown, 022 scope-violation). Remaining: 023 `.harness/.lock` mutex, 024 `sync_harness` orphan detection, 025 integration test `test_parallel_invoke.py`.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → **160** across phases so far.

---
*Updated: 2026-04-20T01:50:00Z*
