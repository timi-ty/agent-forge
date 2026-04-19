# Harness Checkpoint

## Last Completed
**unit_030 (PHASE_007):** [templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) rewritten whole-file to mirror the unit_029 command-doc batch-driven structure in the compact-template style.

- **12 monotonic sections 0–11** matching the command doc verbatim (Detect Host Tool → Turn Ends).
- **Sections 5 and 6** are the only top-level branches (in-tree fast path vs worktree fan-out); sections 7–11 converge.
- **`fleet.mode` transitions** documented at section 3 (guard), section 5 (idle vs dispatched), and section 8 (merging → idle).
- **Section 6 in-tree** carries the compressed capabilities from earlier phases (Exploration keywords, multi-file parallel-edit threshold, parallel Layer 1+Layer 2 validation when the config flag is on).
- **Section 6 fan-out** dispatches one `Agent(subagent_type: "harness-unit")` per unit in a single assistant message; relies on the `templates/claude-code/agents/harness-unit.md` contract for the full allowlist/workflow/report-schema — briefing hands over identity only.
- **Section 10 Commit** carries the parallel code-review + commit-agent-changes dispatch rule at phase close (pre-satisfies unit_032).
- **Section 11 Turn Ends** carries the ISSUE_002 /loop workaround note for Claude Code; Cursor hook behavior preserved.

121 lines (compact template style); zero "sequential path / parallel path" fork language.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_031 (PHASE_007):** Document one-turn-per-batch semantics in [skills/development-harness/references/architecture.md](skills/development-harness/references/architecture.md) — a new paragraph stating `session_count` increments once per turn regardless of batch size, and linking back to PHASE_007's rewrite rationale. Short, tight; closes the docs side of PHASE_007. After 031 lands, unit_032 (parallel phase-review dispatch wiring) is already pre-satisfied by unit_029 + unit_030 — it becomes a grep-verify formality. Unit_033 (integration test `test_invoke_rewrite`) closes the phase.

## Blocked By
None.

## Evidence
- [skills/development-harness/templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md): 121 LOC (whole-file rewrite).
- Grep: 12 monotonic `## N.` section headings 0 → 11 (lines 11, 20, 28, 35, 43, 61, 71, 77, 83, 93, 103, 115); zero "sequential path"/"parallel path" matches; `fleet.mode` at sections 3/5/8.
- `python -m unittest discover skills/development-harness/scripts/tests` → 171/171 pass (docs-only; test suite unchanged).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot. Both invoke docs now explicitly point Claude Code users at `/loop /invoke-development-harness` for multi-turn runs. The proper fix (retire the Stop-hook-as-driver for Claude Code) remains scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_007 PR opens after unit_033.
- **Branch:** `feat/phase-007-invoke-rewrite`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 30 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_007 progress: **2/5 units done**. Remaining: 031 architecture.md paragraph, 032 parallel phase-review dispatch verification (pre-satisfied; mostly grep formality), 033 integration test `test_invoke_rewrite` (closes the phase).
- Test-suite count unchanged at 171 (PHASE_007 has been docs-only so far; 033 will add the integration test).

---
*Updated: 2026-04-20T04:20:00Z*
