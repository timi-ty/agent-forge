# Harness Checkpoint

## Last Completed
**unit_040 (PHASE_009) — PHASE_009 CLOSED.** Concurrent merge serialization proven end-to-end across real OS processes, not just threads.

- **Pre-existing coverage from PHASE_005 unit_023** still green: `TestLockContention` in [test_merge_batch.py](skills/development-harness/scripts/tests/test_merge_batch.py) holds 4 cases — two-thread contention, exception-path cleanup, stale-lock takeover, and fresh-lock timeout.
- **Two new unit_040 cases** close the "two `merge_batch.py` invocations" wording in the acceptance:
  - `test_two_subprocess_acquirers_serialize_on_disk_lock` — spawns a Python subprocess that acquires [_MergeLock](skills/development-harness/scripts/merge_batch.py) against the same `.harness/.lock`, signals `HELD` on stdout, sleeps 0.5s, releases. The main process then acquires the same lock in-process and asserts elapsed ≥ 0.4s, proving OS-level `O_EXCL` semantics hold across processes — the production scenario when two CLI invocations race from two shells or schedulers. PIPE handles explicitly closed; `python -W error::ResourceWarning` confirms no Python 3.12 handle leaks.
  - `test_lock_path_is_exactly_harness_dot_lock` — pins the on-disk lock location at `<root>/.harness/.lock`. If someone moves `LOCK_FILENAME` or the harness-dir layout, cross-process serialization would silently break (each invocation would acquire a different file); this test trips first.

### PHASE_009 at a glance
| Unit | Done | Evidence |
|------|------|----------|
| unit_037 | Session kill switch | `safety_rails.py` + 15 tests + both hooks' `_stop()` sweeps |
| unit_038 | Batch-of-1 no-special-case | 3 grep-as-test cases pin invoke.md + workspace-commands gating |
| unit_039 | Scope-violation always-on policy | Policy section in `phase-contract.md` + 3 policy-presence tests |
| unit_040 | Cross-process merge lock | 2 subprocess-level tests + lock-location pin |

Suite: 183 → 198 → 201 → 204 → **206** across the phase.

### PR review checklist (pr-review-checklist.md)
- [x] All units have `validation_evidence` in phase-graph.json
- [x] No linter/type errors in changed files (stdlib-only Python)
- [x] Codebase patterns followed (testing style matches existing harness test modules)
- [x] Unit tests pass (206/206)
- [x] Integration tests pass (pre-existing `test_invoke_rewrite.py` cases cover the integration half of unit_038)
- [x] Not deploy-affecting (skill distribution repo; `config.json` deployment target is `"none"`)
- [x] Phase doc + checkpoint + state current
- [x] All changes committed; PR to be opened next

## What Failed (if anything)
None.

## What Is Next
**Open PHASE_009 PR** (`feat/phase-009-safety-rails` → `main`), run the `code-review` skill, squash-merge per [harness-git.md](.claude/rules/harness-git.md) autonomous-merge authorization.

**Then PHASE_010 unit_041:** Extend [skills/development-harness/templates/checkpoint-template.md](skills/development-harness/templates/checkpoint-template.md) with a Batch section (batch ID, mode, per-unit status and branch, conflicts summary) so live invoke turns render batch state visibly in the checkpoint. PHASE_010 is observability — three units total (041 checkpoint batch section, 042 logs layout, 043 status summarizer).

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/tests/test_merge_batch.py](skills/development-harness/scripts/tests/test_merge_batch.py): +2 cases in `TestLockContention`.
- [skills/development-harness/scripts/merge_batch.py](skills/development-harness/scripts/merge_batch.py) `_MergeLock` unchanged; unit_040 is test-only.
- `python -m py_compile skills/development-harness/scripts/tests/test_merge_batch.py` exits 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.test_merge_batch.TestLockContention -v` → **6/6** in 2.2s.
- `python -W error::ResourceWarning -m unittest ...test_two_subprocess_acquirers_serialize_on_disk_lock` → OK, no handle-leak warnings.
- `python -m unittest discover skills/development-harness/scripts/tests` → **206/206** (up from 204) in 34.7s.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_009 PR opens now (phase closed).
- **Branch:** `feat/phase-009-safety-rails` → squash-merge to `main`.
- **Next branch:** `feat/phase-010-observability` (to be cut after PHASE_009 squashes in).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 38 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_009 progress: **4/4 units done** — phase CLOSED.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → **206** across phases so far.

---
*Updated: 2026-04-20T07:30:00Z*
