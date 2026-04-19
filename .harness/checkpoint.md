# Harness Checkpoint

## Last Completed
**unit_023 (PHASE_005):** `.harness/.lock` O_EXCL mutex now wraps every `merge_batch()` call. Two concurrent invokers cannot interleave merges — the second **blocks** until the first releases.

- **New `_MergeLock` context manager** in [merge_batch.py](skills/development-harness/scripts/merge_batch.py):
  - Backed by `os.open(path, O_CREAT | O_EXCL | O_WRONLY)` on `<root>/.harness/.lock`.
  - First acquirer wins immediately; subsequent acquirers poll on `lock_poll_interval` (default 0.1s) until the file is unlinked (normal release) or its mtime exceeds `stale_after_seconds` (take-over after a crashed holder).
  - If `lock_timeout` (default 300s) elapses without acquisition, raises `MergeError` with a descriptive message; the pre-existing lock file is preserved (not stomped).
  - Lock body is `"<pid> <iso_ts>\n"` for human inspection and stale-detection debugging.
  - `__exit__` always calls `unlink`, so the lock is released on exception paths too — verified by `test_release_removes_lock_file_even_on_exception`.
- **Wiring:** `merge_batch()` now wraps its full flow in `with _MergeLock(root, timeout=..., stale_after_seconds=..., poll_interval=...)`; the original body moved to `_merge_batch_locked`. CLI gained `--lock-timeout` and `--lock-stale-after` flags.
- **Backward compatibility:** the lock wrapper is transparent to existing tests. All 32 existing `test_merge_batch` + `test_scope_violation` cases pass unchanged — fresh tempdirs per test guarantee no cross-test contention.

**Test coverage:** 4 new cases in `TestLockContention` in [test_merge_batch.py](skills/development-harness/scripts/tests/test_merge_batch.py).
- `test_second_acquirer_blocks_until_first_releases` — thread A acquires and holds for 0.4s; thread B blocks then acquires. Event-barrier ensures A owns the lock before B tries, so the test is deterministic regardless of scheduler jitter. Asserts `a_time < 0.2s` (first is immediate) and `b_time >= 0.3s` (second waited).
- `test_release_removes_lock_file_even_on_exception` — raising `RuntimeError` inside the `with` block still unlinks the lock file.
- `test_stale_lock_is_taken_over` — writes a lock file with mtime 10000s old; acquire with `stale_after=300` completes in <0.5s.
- `test_timeout_raises_merge_error_when_lock_is_fresh` — pre-existing fresh lock, `lock_timeout=0.3s`; `merge_batch()` raises `MergeError` after ≥0.25s wall-clock with "timed out" in the error text; the pre-existing lock file is NOT removed.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_024 (PHASE_005):** Extend [skills/development-harness/scripts/sync_harness.py](skills/development-harness/scripts/sync_harness.py) to detect:
1. **Orphaned worktrees on disk** — directories under `.harness/worktrees/` that have no matching entry in `state.execution.fleet.units`.
2. **Stale fleet entries** — units in `state.execution.fleet.units` whose `worktree_path` no longer exists on disk.
3. **Orphan `harness/batch_*/` branches** — branches matching the naming convention with no fleet entry.

Add new cases to `test_sync_harness.py` covering each detection path. Report these divergences in the existing `state.drift.divergences` array so the existing drift-surface patterns keep working.

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/merge_batch.py](skills/development-harness/scripts/merge_batch.py): new `_MergeLock` class + `_merge_batch_locked` factoring; `merge_batch()` signature adds `lock_timeout`, `lock_stale_after`, `lock_poll_interval` kwargs with documented defaults.
- [skills/development-harness/scripts/tests/test_merge_batch.py](skills/development-harness/scripts/tests/test_merge_batch.py): new `TestLockContention` class with 4 cases.
- `python -m py_compile skills/development-harness/scripts/merge_batch.py` exits 0 (0.14s).
- `python -m unittest skills.development-harness.scripts.tests.test_merge_batch.TestLockContention` passes 4/4 (1.6s).
- `python -m unittest discover skills/development-harness/scripts/tests` passes **164/164** (up from 160 at end of unit_022) in 34.5s.

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
- `session_count` is 23 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_005 progress: **5/7 units done** (019 dispatch, 020 merge, 021 teardown, 022 scope-violation, 023 lock mutex). Remaining: 024 `sync_harness` orphan detection, 025 integration test `test_parallel_invoke.py`.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → **164** across phases so far.

---
*Updated: 2026-04-20T02:10:00Z*
