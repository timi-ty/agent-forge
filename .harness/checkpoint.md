# Harness Checkpoint

## Last Completed
**unit_034 (PHASE_008):** Claude Code stop-hook now has a **fleet-mode guard**. A previous turn that crashed mid-batch leaves `state.execution.fleet.mode` at `"dispatched"` or `"merging"`; the hook now stops immediately in that case instead of trying to continue into an inconsistent state.

- **Code change:** [templates/claude-code/hooks/continue-loop.py](skills/development-harness/templates/claude-code/hooks/continue-loop.py) — new guard between "read state.json" and "check loop budget / blockers / open_questions". Reads `execution.fleet.mode` with a safe chain (`(execution.get("fleet") or {}).get("mode", "idle")`) so v1-style state with no `fleet` block is treated as idle for backward compatibility. If mode isn't idle, calls `_stop(cwd)` which deletes `.invoke-active` and exits 0.
- **Authority-chain docstring** updated to reflect the new step.

**Test coverage:** new [test_continue_loop_claude.py](skills/development-harness/scripts/tests/test_continue_loop_claude.py) (200 LOC, 5 cases across 2 classes) runs the hook as a subprocess with controlled stdin payloads.
- **`TestFleetModeGuard` (4 cases)** — dispatched stops + removes flag; merging stops + removes flag; idle falls through (doesn't short-circuit); missing fleet block treated as idle.
- **`TestFleetGuardDoesNotMaskContinuePath` (1 case, positive control)** — with fleet.mode idle AND a fully-seeded harness (phase-graph.json, a one-off `select_next_unit.py` stub matching the hook's JSON contract, `checkpoint.next_action` containing the unit id), the hook reaches exit 2 with `{"decision": "block"}` and preserves `.invoke-active`. Proves the guard doesn't falsely trigger on idle state — the one risk of an overly eager guard.

Test technique isolates the hook from selector evolution by shipping a one-off `select_next_unit.py` stub rather than depending on the real selector's current shape.

## What Failed (if anything)
First test run had all 5 failing because `HOOK_PATH` used `parents[3]` instead of `parents[2]` — the test file is 3 levels deep inside `skills/development-harness/scripts/tests/`, not 4. Fixed by changing to `parents[2]` so `SKILL_ROOT` resolves to `skills/development-harness/`. Re-run: 5/5 green.

## What Is Next
**Complete unit_035 (PHASE_008):** Mirror the fleet-mode guard into [templates/hooks/continue-loop.py](skills/development-harness/templates/hooks/continue-loop.py) (Cursor variant). Same logic adapted for Cursor's hook protocol — Cursor reads `workspace_roots` from input_data (not `cwd`) and signals stop by printing `{}` (not exit 0). Add `test_continue_loop_cursor.py` with the same five cases against the Cursor payload shape.

## Blocked By
None.

## Evidence
- [skills/development-harness/templates/claude-code/hooks/continue-loop.py](skills/development-harness/templates/claude-code/hooks/continue-loop.py): fleet-mode guard added between state-read and budget-check.
- [skills/development-harness/scripts/tests/test_continue_loop_claude.py](skills/development-harness/scripts/tests/test_continue_loop_claude.py): new 200-line test module, 5 cases.
- `python -m py_compile` on both files exits 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.test_continue_loop_claude -v` → 5/5 pass (0.5s).
- `python -m unittest discover skills/development-harness/scripts/tests` → **178/178** pass (up from 173 at PHASE_007 end) in 39.6s.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot. The fleet-mode guard added in unit_034 is **complementary** to ISSUE_002's fix — the guard is a precondition check that works regardless of whether the hook drives continuation or not. `unit_bugfix_002` at head of PHASE_011 will retire the block-continue part of the hook for Claude Code, but the fleet-mode guard remains a valuable precondition regardless.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_008 PR opens after unit_036.
- **Branch:** `feat/phase-008-stop-hook-fleet-awareness`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 33 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_008 progress: **1/3 units done** (034 Claude Code hook guard). Remaining: **035** Cursor mirror, **036** manual verification checklist (documented in the phase doc's Rollback section, no code).
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → **178** across phases so far.

---
*Updated: 2026-04-20T05:05:00Z*
