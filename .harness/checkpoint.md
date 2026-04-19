# Harness Checkpoint

## Last Completed
**unit_037 (PHASE_009):** Session-scoped safety rails landed — the harness now auto-degrades to in-tree after two bad batches in a session.

- **New module** [safety_rails.py](skills/development-harness/scripts/safety_rails.py) (165 LOC, stdlib-only):
  - `record_failure(root, category, unit_id, now)` — appends a JSON line to `.harness/.parallel-failures.jsonl` and writes the kill switch at `.harness/.parallel-disabled` when the count of failures in `COUNTED_CATEGORIES = ("scope_violation", "ambiguity")` reaches `KILL_SWITCH_THRESHOLD = 2`.
  - `is_parallel_disabled(root)` — presence check.
  - `clear_safety_rails(root)` — idempotent removal of both files.
  - CLI: `record` / `status` / `clear` subcommands for manual operator control.
- **Failures in non-counted categories** (e.g., `validation`, `infrastructure`) are still logged for observability but **do not count toward the threshold** — only the two kill-switch categories do. `test_other_categories_do_not_pollute_counted_total` pins this invariant.
- **Hook updates:** both [Claude Code](skills/development-harness/templates/claude-code/hooks/continue-loop.py) and [Cursor](skills/development-harness/templates/hooks/continue-loop.py) `continue-loop.py` `_stop()` helpers now remove `.invoke-active` **and** `.parallel-disabled` **and** `.parallel-failures.jsonl` in one sweep, so session-scoped safety-rail state is cleared whenever the hook decides to stop.

**Test coverage:** 15 new cases across 5 classes in [test_safety_rails.py](skills/development-harness/scripts/tests/test_safety_rails.py):
- `TestRecordFailureThreshold` (6) — below-threshold no-op; at-threshold trips; above-threshold idempotent; scope_violation + ambiguity mix correctly; non-counted categories don't count; counted + non-counted interleave correctly.
- `TestHelpers` (3) — `is_parallel_disabled` reflects file; `clear_safety_rails` removes both files; `clear_safety_rails` idempotent on missing files.
- `TestCliSmoke` (2) — round-trip record + status; clear via CLI.
- `TestHookStopClearsSafetyRails` (2) — **both** Claude Code and Cursor hooks' `_stop()` wipe the rail files via subprocess end-to-end (seeded state + controlled stdin).
- `TestConstants` (2) — pins `KILL_SWITCH_THRESHOLD == 2` and the counted-categories set.

**Pre-existing hook tests pass unchanged.** The 10 cases in `test_continue_loop_{claude,cursor}.py` still pass — the additional `unlink` calls in `_stop()` target missing files in those tests and the `try/except OSError` handles cleanly.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_038 (PHASE_009):** Verify batch-of-1 uses the in-tree path (no special-case branch in the invoke doc) AND integration test asserts final state equivalence. Most of the acceptance is **pre-satisfied** by PHASE_007's unit_029 rewrite (which collapsed the sequential/parallel fork) and unit_033's `TestBatchOfOneDispatchModeEquivalence` (which asserted in-tree vs worktree produce equivalent final state). This unit becomes a grep-verify of the invoke doc + optional augmentation of the existing equivalence test.

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/safety_rails.py](skills/development-harness/scripts/safety_rails.py): new 165-line module.
- [skills/development-harness/scripts/tests/test_safety_rails.py](skills/development-harness/scripts/tests/test_safety_rails.py): new 225-line test module, 15 cases.
- Both hook `_stop()` helpers updated with the safety-rail sweep.
- `python -m py_compile` → 0 (~0.1s) on all 4 changed/new files.
- `python -m unittest skills.development-harness.scripts.tests.test_safety_rails -v` → 15/15 in 0.7s.
- `python -m unittest discover skills/development-harness/scripts/tests` → **198/198** (up from 183 at PHASE_008 end) in 38.4s.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_009 PR opens after unit_040 (closes the phase).
- **Branch:** `feat/phase-009-safety-rails`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 35 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_009 progress: **1/4 units done** (037 kill switch). Remaining: 038 batch-of-1 equivalence verification, 039 scope-violation always-on policy docs, 040 concurrent merge serialization test.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → **198** across phases so far.

---
*Updated: 2026-04-20T05:45:00Z*
