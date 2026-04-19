# Harness Checkpoint

## Last Completed
**PHASE_008 complete (all 3 units).** The Stop hook is now fleet-aware on both Cursor and Claude Code. A turn that crashed mid-batch can no longer trick the hook into auto-continuing into an inconsistent state.

- **unit_034** — fleet-mode guard in [Claude Code continue-loop.py](skills/development-harness/templates/claude-code/hooks/continue-loop.py); new [test_continue_loop_claude.py](skills/development-harness/scripts/tests/test_continue_loop_claude.py) with 5 cases.
- **unit_035** — mirror in [Cursor continue-loop.py](skills/development-harness/templates/hooks/continue-loop.py) with the Cursor protocol (always exits 0; stop = `print({})`, continue = `print({"followup_message": ...})`); new [test_continue_loop_cursor.py](skills/development-harness/scripts/tests/test_continue_loop_cursor.py) with 5 cases structurally mirroring the Claude Code test.
- **unit_036** — the unit-test half of the acceptance is covered by unit_034 + unit_035's 10 cases total (dispatched + merging + idle-falls-through + missing-fleet-treated-as-idle + positive-control reaches-continue, per hook variant). The manual-verification half landed as a new subsection under "Rollback / Failure Considerations" in [PHASES/PHASE_008_stop-hook-fleet-awareness.md](PHASES/PHASE_008_stop-hook-fleet-awareness.md) — a step-by-step checklist for mid-batch kill → new session → hook stops cleanly → `/sync-development-harness` surfaces orphans → `teardown_batch.py --batch-id <id>` recovers → `/invoke-development-harness` restarts cleanly.

**Test-suite growth this phase:** 173 → **183** (+10 hook tests). The hook tests use subprocess + controlled stdin payloads + observable contract (exit code / stdout JSON / `.invoke-active` presence); they ship a one-off `select_next_unit.py` stub for the positive-control case so the tests don't drift when the real selector evolves.

## What Failed (if anything)
First run of `test_continue_loop_claude.py` had a `HOOK_PATH` bug (`parents[3]` vs `parents[2]`) that made every case fail with a "no such file" stderr. Fixed by adjusting to `SKILL_ROOT = parents[2]`; the Cursor test was written correctly from the start using the fixed pattern.

## What Is Next
**Run PHASE_008 phase completion review** (pr-review-checklist + code-review skill), open the phase PR, autonomous squash-merge per [harness-git.md](.claude/rules/harness-git.md). After merge, advance to **unit_037 (PHASE_009, safety-rails-and-automatic-fallback)** — a session-scoped kill switch that writes `.harness/.parallel-disabled` after 2 `scope_violation` or `ambiguity` failures in a session; cleared when `.invoke-active` clears.

## Blocked By
None.

## Evidence
- [skills/development-harness/templates/claude-code/hooks/continue-loop.py](skills/development-harness/templates/claude-code/hooks/continue-loop.py) + [templates/hooks/continue-loop.py](skills/development-harness/templates/hooks/continue-loop.py): fleet-mode guards, identical logic adapted per tool protocol.
- [skills/development-harness/scripts/tests/test_continue_loop_claude.py](skills/development-harness/scripts/tests/test_continue_loop_claude.py) + [test_continue_loop_cursor.py](skills/development-harness/scripts/tests/test_continue_loop_cursor.py): 5 cases each, 10 cases total.
- [PHASES/PHASE_008_stop-hook-fleet-awareness.md](PHASES/PHASE_008_stop-hook-fleet-awareness.md): Rollback section expanded with the manual-verification checklist.
- `python -m unittest discover skills/development-harness/scripts/tests` → **183/183** pass (up from 173 at PHASE_007 end) in 44.5s.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot. PHASE_008's fleet-mode guard is **complementary** to the ISSUE_002 fix — the guard is a precondition check that remains valuable regardless of whether the hook drives continuation. `unit_bugfix_002` at head of PHASE_011 will retire the block-continue part; the fleet-mode guard stays.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_008 PR opens now with all three units.
- **Branch:** `feat/phase-008-stop-hook-fleet-awareness` (delete on merge).
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 34 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE progress so far: PHASE_001–008 complete (36 units). Remaining: PHASE_009–013 (≈22 units).
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → **183** across phases so far.

---
*Updated: 2026-04-20T05:20:00Z*
