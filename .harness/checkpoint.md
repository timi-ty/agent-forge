# Harness Checkpoint

## Last Completed
**unit_019 (PHASE_005):** First code-bearing unit since PHASE_002. New [skills/development-harness/scripts/dispatch_batch.py](skills/development-harness/scripts/dispatch_batch.py) lands with a complete unit-test suite.

- **Public API:** `dispatch_batch(batch_result, root, state=None, now=None)` consumes the `{batch_id, batch, excluded}` dict from `compute_parallel_batch.compute_batch` and, per unit in `batch`, runs `git worktree add -b harness/<batch_id>/<unit_id> .harness/worktrees/<batch_id>/<unit_id> HEAD` (via `subprocess`), seeds `<worktree>/.harness/WORKTREE_UNIT.json` with `batch_id` / `unit_id` / `phase_id` / `touches_paths`, and appends a `status="running"` entry to the returned fleet block.
- **State mutation:** when a `state` dict is passed, `state.execution.fleet` is replaced in place with `{mode: "dispatched", batch_id, units: [...]}`. Every entry matches the v2 schema: `unit_id`, `phase_id`, `worktree_path`, `branch`, `status`, `started_at`, `ended_at=None`, `agent_summary_path=None`, `conflict=None`.
- **Atomic failure semantics:** any `subprocess.CalledProcessError` / `OSError` / `KeyError` during per-unit processing triggers `_rollback(root, created)`, which best-effort removes every worktree + branch created so far, then re-raises as `DispatchError`. Pre-existing branches are never touched.
- **CLI:** `--batch <file>` `--root <dir>` `--state <file>`; prints the fleet block as JSON to stdout; writes back `state.last_updated` + `state.execution.fleet` when `state.json` exists.

**Test coverage:** 9 new cases across 3 classes.
- `TestHappyPath` (5) — worktrees + branches, WORKTREE_UNIT.json contents, v2 fleet-entry shape, empty-batch edge, in-place state mutation.
- `TestAtomicRollback` (2) — pre-created colliding branch on unit_b causes DispatchError and unit_a's worktree is cleanly rolled back; malformed unit (missing `id`) exercises the KeyError rollback path.
- `TestCliSmoke` (2) — end-to-end subprocess run writes state + stdout JSON; `--help` runs.

Test fixtures use real `git init` + one commit in a tempdir because worktree ops require a commit graph. This is the first git-subprocess-using test module in the suite.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_020 (PHASE_005):** New [skills/development-harness/scripts/merge_batch.py](skills/development-harness/scripts/merge_batch.py) — serial fan-in via `git merge --no-ff harness/<batch_id>/<unit_id> -m "harness: merge <unit_id>"`; conflict strategies (`abort_batch` aborts on first conflict, `serialize_conflicted` requeues conflicted units); repo-wide post-merge validation (lint + typecheck + merged units' unit tests, in parallel when the flag is on); `git reset --hard <pre-merge-ref>` rollback on post-merge failure; `git worktree remove` + branch delete on success. Tests under `test_merge_batch.py` cover happy path, both conflict strategies, post-merge-failure rollback, and a contention case for the `.harness/.lock` mutex that lands with unit_023.

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/dispatch_batch.py](skills/development-harness/scripts/dispatch_batch.py): new 207-line module with module docstring, public `dispatch_batch`, `DispatchError`, private helpers (`_create_worktree`, `_seed_worktree_unit_json`, `_remove_worktree`, `_rollback`), and a CLI `main()`.
- [skills/development-harness/scripts/tests/test_dispatch_batch.py](skills/development-harness/scripts/tests/test_dispatch_batch.py): new 194-line test module, 9 cases, tempdir git-repo fixtures.
- `python -m py_compile skills/development-harness/scripts/dispatch_batch.py skills/development-harness/scripts/tests/test_dispatch_batch.py` exits 0 (0.14s).
- `python -m unittest skills.development-harness.scripts.tests.test_dispatch_batch -v` passes 9/9 (3.5s).
- `python -m unittest discover skills/development-harness/scripts/tests` passes **118/118** (up from 109 at PHASE_004 end) in 11.3s.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; this session continues under `/loop /invoke-development-harness`. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_005 PR opens after unit_025 (7 units total).
- **Branch:** `feat/phase-005-worktree-dispatch`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 19 / `loop_budget` 12 — `/loop` driver ongoing. Budget knob revisit scheduled in `unit_bugfix_002` / PHASE_011 doc pass.
- **PHASE_005 is the biggest code-bearing phase of the roadmap** (7 units, 3 new scripts + 1 script extension + 1 integration test). The test-suite count will continue to climb through the rest of the phase.

---
*Updated: 2026-04-20T00:40:00Z*
