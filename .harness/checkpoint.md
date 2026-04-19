# Harness Checkpoint

## Last Completed
**unit_031 AND unit_032 complete in one turn.** PHASE_007 is now 4/5 done; only the closing integration test remains.

### unit_031 — one-turn-per-batch semantics in architecture.md

Added a new `## Batch Semantics — one turn per batch` subsection to [references/architecture.md](skills/development-harness/references/architecture.md) between Loop Mechanics and Git Integration. Three load-bearing statements:

1. A single invoke turn processes a whole **batch**, not a single unit.
2. **`execution.session_count` increments by exactly 1 per turn, regardless of batch size.** `loop_budget` is denominated in turns, not units.
3. The full `idle → dispatched → merging → idle` fleet transition completes within one turn in the worktree path; the hook never sees a partial fleet.

Links forward to `commands/invoke.md` Steps 4–9 and `parallel-execution.md` (the latter lands in PHASE_011 unit_047).

### unit_032 — parallel phase-review dispatch (grep-verified, pre-satisfied)

The acceptance criterion ("Phase completion review step in both docs explicitly says 'single assistant message with both Agent calls'") is already satisfied by the unit_029 + unit_030 rewrites. Grep confirms:
- [commands/invoke.md:262](skills/development-harness/commands/invoke.md#L262) — "dispatch them **in one assistant message** with two `Agent(subagent_type: "general-purpose")` tool calls".
- [templates/workspace-commands/invoke-development-harness.md:111](skills/development-harness/templates/workspace-commands/invoke-development-harness.md#L111) — same rule compressed to the template style.

Both docs include the concrete two-call code sample and the serial fallback for when only one skill is installed or no phase closed this turn. No additional file changes were required; the unit is marked complete with the grep evidence.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_033 (PHASE_007, closes the phase):** New integration test [tests/integration/test_invoke_rewrite.py](skills/development-harness/scripts/tests/integration/test_invoke_rewrite.py) — a fixture 3-unit parallel phase that completes in **one turn** via the new batch-driven pipeline. Also verify that a batch-of-1 in-tree run and a batch-of-1 worktree run produce the same final state (unit_029 left a hook for this in Step 4's "Pick the dispatch mode" section; PHASE_009 has a dedicated regression test for the equivalence claim, but unit_033 plants the first end-to-end assertion). Test asserts final `phase-graph.json` shows all units `"completed"` with evidence and `fleet.mode == "idle"`. **When 033 lands, open the PHASE_007 PR.**

## Blocked By
None.

## Evidence
- [skills/development-harness/references/architecture.md:81-89](skills/development-harness/references/architecture.md#L81-L89): new Batch Semantics subsection (session_count once-per-turn + fleet transition + loop_budget in turns).
- [skills/development-harness/commands/invoke.md:262](skills/development-harness/commands/invoke.md#L262) and [workspace-commands template:111](skills/development-harness/templates/workspace-commands/invoke-development-harness.md#L111): parallel phase-review dispatch rule.
- `python -m unittest discover skills/development-harness/scripts/tests` → 171/171 pass (no additional file changes in unit_032; docs-only turn).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot. Both invoke docs now point Claude Code users at `/loop /invoke-development-harness`; the full fix (retire the Stop-hook-as-driver) is `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_007 PR opens after unit_033 (the integration test) — the next turn.
- **Branch:** `feat/phase-007-invoke-rewrite`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 31 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_007 progress: **4/5 units done** (029 invoke rewrite, 030 workspace-commands mirror, 031 architecture.md paragraph, 032 parallel phase-review dispatch grep-verified). Remaining: **033 integration test** (closes the phase).
- Test-suite count at 171 and will climb again with unit_033's integration test.

---
*Updated: 2026-04-20T04:35:00Z*
