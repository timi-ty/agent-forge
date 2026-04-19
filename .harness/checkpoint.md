# Harness Checkpoint

## Last Completed
**unit_011 (PHASE_003):** Inserted **Step 6: Exploration (conditional)** in [skills/development-harness/commands/invoke.md](skills/development-harness/commands/invoke.md).

- New step sits between the existing "Step 5: Read Phase Context" and the (now-renumbered) "Step 7: Plan the Unit".
- Lists the five **trigger keywords** that require a pre-plan Explore dispatch: `refactor`, `extend`, `fix`, `migrate`, `update`.
- Lists the five **skip keywords** (from-scratch units): `add`, `new`, `create`, `insert`, `scaffold`.
- Shows a concrete `Agent(subagent_type: "Explore", thoroughness: "medium")` call with a reusable prompt template covering files, tests to change, conventions to match, and prior-art gotchas.
- Explains how to absorb the agent's report into Step 7's plan and that the main agent — not the Explore agent — still does the editing, testing, and commit.

Side work: renumbered old Steps 6–12 to 7–13 (and subsection labels 9a/9b/9c → 10a/10b/10c), and updated three internal cross-references so the numbering stays coherent.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_012 (PHASE_003):** Mirror the Exploration step in [skills/development-harness/templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) so the workspace-installed copy is consistent with the canonical command doc landed in unit_011.

## Blocked By
None.

## Evidence
- [skills/development-harness/commands/invoke.md](skills/development-harness/commands/invoke.md): `+42 / -7` for the new Step 6 block plus renumbering and cross-reference fixes.
- Grep: `## Step 6: Exploration` at line 94; the five trigger keywords on consecutive bullet lines 102–106; `Agent(` with `subagent_type: "Explore"` at line 115.
- Grep: every `## Step N` heading appears exactly once, in order 0 → 13. No stale step numbers remain in prose or sub-section labels.
- `python -m unittest discover skills/development-harness/scripts/tests` → 109/109 pass (docs-only change; test suite unaffected).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Stop-hook portability on Windows when only `python` is on PATH. Workspace-level fix active; skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_003 PR opens after unit_015.
- **Branch:** `feat/phase-003-intra-unit-delegation`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `loop_budget` was bumped from 10 to 12 in state.json; revisit as a proper config knob in PHASE_011's doc pass.

---
*Updated: 2026-04-19T21:50:00Z*
