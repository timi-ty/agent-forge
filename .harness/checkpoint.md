# Harness Checkpoint

## Last Completed
**unit_020 (PHASE_005):** Serial fan-in merge infrastructure landed. Pair with `dispatch_batch.py` (unit_019) and PHASE_005 has the two largest moving pieces in place.

- **Public API:** `merge_batch(state, root, *, conflict_strategy="abort_batch", run_post_merge_validation=None, now=None)` in [skills/development-harness/scripts/merge_batch.py](skills/development-harness/scripts/merge_batch.py).
  - Flips `fleet.mode` to `"merging"`, captures `pre_merge_ref = git rev-parse HEAD`.
  - Iterates `fleet.units` in list order running `git merge --no-ff harness/<batch_id>/<unit_id> -m "harness: merge <unit_id>"`.
  - On conflict, always runs `git merge --abort` first, then applies `conflict_strategy`:
    - **`abort_batch`** (default) — failed unit carries `status="failed"` + `conflict={paths, strategy_applied}`; remaining units are flagged `status="failed"` with `conflict=null` (they were skipped, not conflicted).
    - **`serialize_conflicted`** — failed unit keeps `status="running"` with `conflict={paths, strategy_applied}` so its worktree/branch survive for a later batch. Remaining units still get merged.
  - Post-merge validator is a caller-injected callable `(root, merged_unit_ids) -> (ok_bool, evidence_str)`. Default `_noop_validate` always succeeds; the CLI does NOT hardcode a real validator (that wiring belongs in `invoke.md` Step 9's post-merge hook, not in `merge_batch` itself).
  - On validation failure: `git reset --hard <pre_merge_ref>` restores HEAD; every previously merged unit downgrades to `status="failed"` with `conflict.strategy_applied = "post_merge_validation_failed"`; return `outcome="validation_failed"`.
  - On success: every `status="merged"` unit has its worktree removed (`git worktree remove --force`) and branch deleted (`git branch -D`). `fleet.mode` ends at `"idle"`.
- **Return shape:** `{batch_id, outcome, merged, conflicted, skipped, validation_evidence}` where `outcome ∈ {"ok", "partial", "aborted", "validation_failed", "all_conflicted", "empty"}`.
- **CLI:** `--state <file>`, `--root <dir>`, `--conflict-strategy {abort_batch, serialize_conflicted}`. Persists state via `write_json(state_path, state)` and stamps `state.last_updated`.

**Scope boundaries:** scope-violation detection (unit_022) and `.harness/.lock` mutex (unit_023) are separate units with clean insertion points — pre-per-unit for scope checks, wrapper layer for the lock.

**Test coverage:** 16 new cases in [test_merge_batch.py](skills/development-harness/scripts/tests/test_merge_batch.py) across 7 classes.
- `TestHappyPath` (5) — all clean, merge-commit messages, branch deletion, empty fleet, mode transitions.
- `TestAbortBatchStrategy` (2) — abort semantics + branch-cleanup asymmetry (merged branch deleted, conflicted and skipped branches preserved).
- `TestSerializeConflictedStrategy` (2) — conflicted unit stays `running` while remaining units merge; conflicted branch preserved.
- `TestPostMergeValidation` (3) — validator receives the right `merged_ids`; `git reset --hard` rollback on failure verified by comparing HEAD SHA before/after; validator not called when no unit merged.
- `TestStrategyValidation` — unknown strategy raises `MergeError`.
- `TestEndToEndWithDispatch` — full `dispatch_batch` → commit in worktree → `merge_batch` cycle, asserting worktrees removed and branches deleted.
- `TestCliSmoke` (2) — `--help` + end-to-end `state.json` write with the CLI binary.

## What Failed (if anything)
One test initially red on first run (`test_empty_fleet_returns_empty_outcome` — fleet.mode stayed `"dispatched"` because I used `fleet.setdefault("mode", "idle")`). Fixed by replacing with an explicit `fleet["mode"] = "idle"` assignment; re-run: 16/16 green.

## What Is Next
**Complete unit_021 (PHASE_005):** New [skills/development-harness/scripts/teardown_batch.py](skills/development-harness/scripts/teardown_batch.py) — idempotent cleanup of worktrees under `.harness/worktrees/` and branches matching `harness/batch_*/`. Must be callable from `/clear`, `/sync`, and error-recovery paths. Acceptance: second run is a no-op; handles missing worktrees and branches gracefully.

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/merge_batch.py](skills/development-harness/scripts/merge_batch.py): new 217-line module.
- [skills/development-harness/scripts/tests/test_merge_batch.py](skills/development-harness/scripts/tests/test_merge_batch.py): new 340-line test module, 16 cases.
- `python -m py_compile` on both new files exits 0 (0.13s).
- `python -m unittest skills.development-harness.scripts.tests.test_merge_batch` passes 16/16 (12.0s).
- `python -m unittest discover skills/development-harness/scripts/tests` passes **134/134** (up from 118 at end of unit_019) in 21.6s.

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
- `session_count` is 20 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_005 progress: 2/7 units done. Next up: `teardown_batch.py` (021), scope-violation detector (022), `.harness/.lock` mutex (023), `sync_harness` orphan detection (024), and `test_parallel_invoke.py` integration test (025).
- Test-suite count has climbed 65 → 83 → 106 → 109 → 118 → **134** across PHASE_001 → PHASE_005 so far.

---
*Updated: 2026-04-20T01:05:00Z*
