# PHASE_005: Worktree Dispatch and Merge Infrastructure

## Objective
Build the mechanics of a parallel batch — worktree creation, branch seeding, serial fan-in merge, scope-violation detection, cleanup — as standalone scripts, fully unit- and integration-tested, before any of this is wired into the live invoke flow.

## Why This Phase Exists
The parallel execution model hinges on four operations the current harness cannot perform: create isolated worktrees per unit, merge per-unit branches serially, detect when a sub-agent exceeded its declared blast radius, and clean up after a failed batch. Each needs its own script with clear CLI contracts so PHASE_007 can wire them in confidently.

## Scope
- New `skills/development-harness/scripts/dispatch_batch.py`:
  - Inputs: batch JSON from `compute_parallel_batch.py`.
  - Per unit: `git worktree add -b harness/<batch_id>/<unit_id> .harness/worktrees/<batch_id>/<unit_id> HEAD`.
  - Seed worktree with `.harness/WORKTREE_UNIT.json` (`batch_id`, `unit_id`, `phase_id`, declared `touches_paths`).
  - Write `state.json.execution.fleet` entries.
  - Atomic on failure: on any per-unit failure, tear down all worktrees created by this dispatch and error out.
- New `skills/development-harness/scripts/merge_batch.py`:
  - Inputs: batch ID; implicit state via `state.json.execution.fleet`.
  - Serial fan-in — per unit in order: `git merge --no-ff harness/<batch_id>/<unit_id> -m "harness: merge <unit_id>"`.
  - On conflict: `git merge --abort`, record conflicting paths on fleet entry, apply `conflict_strategy` (`abort_batch` or `serialize_conflicted`).
  - Post-merge: run repo-wide lint + typecheck + each merged unit's unit tests (in parallel if `parallel_validation_layers: true`). On failure, `git reset --hard <pre-merge-ref>` and mark batch failed.
  - On success: mark units `completed`, append validation evidence, `git worktree remove`, delete branches.
- New `skills/development-harness/scripts/teardown_batch.py`:
  - Idempotent cleanup of worktrees under `.harness/worktrees/` and branches matching `harness/batch_*/`.
  - Callable from `/clear`, `/sync`, and error recovery paths.
- Scope-violation detector in `merge_batch.py` (runs *before* each merge): `git diff --name-only <merge-base>..<branch>` filtered against declared `touches_paths`. Any file in the diff matching none of the declared globs → unit rejected with `category: "scope_violation"`. The sub-agent's self-report is never trusted for blast radius.
- `.harness/.lock` file-based mutex (O_EXCL) wrapping `merge_batch.py`. Prevents concurrent merges if two invoke sessions somehow collide.
- Extend `skills/development-harness/scripts/sync_harness.py` to detect orphaned worktrees on disk not in `state.fleet`, stale fleet entries whose worktrees are missing, and `harness/batch_*/` branches without fleet entries.
- Integration test `skills/development-harness/scripts/tests/integration/test_parallel_invoke.py`: builds a tmp git repo, sets up a 3-unit fixture phase, runs `dispatch_batch.py` then shell-scripted fake agents that commit canned files in each worktree, then `merge_batch.py`. Asserts final state, clean worktree removal, and no residual branches.

> ⚠️ **Edit target:** `skills/development-harness/**` only. The frozen `.harness/scripts/` in the running harness stays on v1 until bootstrap.

## Non-goals
- Wiring these scripts into the invoke command — PHASE_007.
- Stop-hook fleet awareness — PHASE_008.
- Safety-rail policy (kill switch, auto-downgrade) — PHASE_009.

## Dependencies
- PHASE_001 (new schema fields for fleet and touches_paths).
- PHASE_002 (batcher output consumed by `dispatch_batch.py`).

## User-visible Outcomes
- `python skills/development-harness/scripts/dispatch_batch.py --batch <file>` creates worktrees and updates state.
- `python skills/development-harness/scripts/merge_batch.py --batch-id <id>` performs the serial fan-in and cleanup.
- The integration test runs to completion locally with a fixture repo.

## Units of Work

| ID | Description | Acceptance Criteria | Validation Method | Status |
|----|-------------|--------------------|--------------------|--------|
| unit_019 | `dispatch_batch.py` — worktree + branch creation; `state.fleet` writes; atomic teardown on failure | All worktrees created with correct branch names; WORKTREE_UNIT.json seeded; partial failure rolls back cleanly | `python -m unittest skills.development-harness.scripts.tests.test_dispatch_batch` | pending |
| unit_020 | `merge_batch.py` — serial fan-in; conflict strategies; post-merge validation; rollback | Happy path merges all units in order; `abort_batch` aborts on first conflict; `serialize_conflicted` requeues conflicted units; post-merge failure rolls back to pre-merge ref | `python -m unittest skills.development-harness.scripts.tests.test_merge_batch` | pending |
| unit_021 | `teardown_batch.py` — idempotent cleanup | Second run is a no-op; handles missing worktrees and branches gracefully | `python -m unittest skills.development-harness.scripts.tests.test_teardown_batch` | pending |
| unit_022 | Scope-violation detector | Unit whose branch diff includes files outside declared `touches_paths` is rejected before merge with `category: "scope_violation"` | `python -m unittest skills.development-harness.scripts.tests.test_scope_violation` | pending |
| unit_023 | `.harness/.lock` mutex around `merge_batch.py` | Second concurrent invocation blocks until first releases; on crash, stale lock detection documented | `test_merge_batch` contention case | pending |
| unit_024 | Extend `sync_harness.py` to detect orphans | Orphaned worktrees, stale fleet entries, orphan `harness/batch_*/` branches all reported | `python -m unittest skills.development-harness.scripts.tests.test_sync_harness` — new cases | pending |
| unit_025 | Integration test `test_parallel_invoke.py` | Full dispatch → fake agents → merge cycle on fixture; asserts final state and no residual worktrees/branches | `python -m unittest skills.development-harness.scripts.tests.integration.test_parallel_invoke` | pending |

## Validation Gates
- **Layer 1:** Python syntax valid on all new scripts.
- **Layer 2:** All new unit tests pass.
- **Layer 3:** Integration test passes on a fixture git repo.

## Deployment Implications
Not deploy-affecting.

## Completion Evidence Required
- All new unit tests exit 0.
- Integration test exits 0.
- Manual verification: create a fixture, run `dispatch_batch.py` → check `state.fleet`; run `merge_batch.py` → check commits merged and worktrees removed.

## Rollback / Failure Considerations
New scripts only — no modification to existing invoke flow in this phase, so failure cannot wedge the running harness. If tests fail, revert the phase commits and address before moving to PHASE_007.

## Status
pending
