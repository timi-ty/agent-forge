# Harness Checkpoint

## Last Completed
**unit_013 (PHASE_003)** + **ISSUE_002 injected.**

### unit_013
Multi-file parallel-edit guidance landed in **both** invoke docs.
- [commands/invoke.md](skills/development-harness/commands/invoke.md) Step 8 gains a new `### Multi-file parallel edits` sub-section: **≥4 independent files** threshold, **single assistant message, 2–3 `Agent(subagent_type: "general-purpose")`** fan-out shape, why the range is bounded at 2–3, a group-by-independence rule, and two worked examples (parallel-safe: mirrored templates; NOT-parallel-safe: symbol rename with cascading callsites).
- [templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) section 9 gains a **bold-label** paragraph with the same threshold, shape, grouping rule, and sub-threshold fallback — compressed to the template's single-paragraph style.

### ISSUE_002
User reported auto-continue is unreliable on Claude Code. Investigation validated the root cause with evidence:
- Claude Code's `stop_hook_active` field is a **session-wide one-shot guard**: it flips to True after the first hook-driven continuation and cannot be reset.
- Claude Code's built-in Stop-hook loop-guard enforces the floor — removing the hook's own `stop_hook_active` check just delegates the stop to Claude Code, no opt-out exists.
- The harness's `continue-loop.py` is a line-for-line port of the Cursor variant, whose `followup_message` protocol has no such guard. On Cursor the port works; on Claude Code it structurally cannot drive N-turn autonomy.

Fix captured as **`unit_bugfix_002`** at the head of PHASE_011 (docs-and-templates change; doesn't need PHASE_005 worktree infra):
1. New doc `references/claude-code-continuation.md` explaining the protocol mismatch.
2. Rewrite `templates/claude-code/hooks/continue-loop.py` to a precondition-only shape (no `sys.exit(2)`, no `{"decision": "block"}` — always exit 0 with an advisory).
3. Both invoke docs get a "Claude Code: run under `/loop`" section pointing users at `/loop /invoke-development-harness` as the autonomous-run primitive.
4. `commands/create.md` Phase 5 wires the Claude Code hook as a precondition checker, not a continue-driver.
5. Cursor hook template is unchanged.

**Downstream impact:** PHASE_008 (Stop-hook fleet-awareness, units 034–036) currently assumes Claude Code's hook keeps driving continuation; those units must be re-scoped after `unit_bugfix_002` lands so their fleet-mode checks layer onto the precondition-only shape. This is flagged in the PHASE_011 scope note and in the `unit_bugfix_002` description in phase-graph.json.

## What Failed (if anything)
The `normalize_issues.py` CLI split the pasted issue text by blank line into 10 separate issues, which was wrong for a single conceptual issue. Recovered by deleting ISSUE_002 through ISSUE_011 and writing `ISSUE_002.json` by hand patterned on `ISSUE_001.json`. The normalizer's paragraph-heuristic is a paper cut, not a blocker — worth noting as a future unit if multi-paragraph issues become common.

## What Is Next
**Complete unit_014 (PHASE_003):** Add parallel phase-review dispatch guidance to both invoke docs — during Step 10 (phase completion review), when both the `code-review` and `commit-agent-changes` skills are installed, dispatch them in one assistant message so they run concurrently instead of serially.

## Blocked By
None.

## Evidence
- [.harness/issues/ISSUE_002.json](.harness/issues/ISSUE_002.json): full issue record (severity `high`, suspected phase PHASE_011, suspected unit `unit_bugfix_002`, reproduction steps, root cause, fix approach, regression coverage).
- [.harness/phase-graph.json](.harness/phase-graph.json) PHASE_011: `unit_bugfix_002` added at the head alongside `unit_bugfix_001`, with acceptance criteria and validation method spelled out.
- [PHASES/PHASE_011_documentation.md](PHASES/PHASE_011_documentation.md): Scope section names both bugfix units; Units of Work table carries both as rows above unit_045.
- [.harness/state.json](.harness/state.json) issue counters: `total: 2 / open: 2 / resolved: 0`.

## Open Questions
None. (The ISSUE_002 investigation is resolved; the fix is scoped as a concrete unit.)

## Tracked Issues
- **ISSUE_001** (high, open): Stop-hook portability on Windows when only `python` is on PATH. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; retire Stop-hook-as-driver for Claude Code and use `/loop /invoke-development-harness`. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_003 PR opens after unit_015.
- **Branch:** `feat/phase-003-intra-unit-delegation`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 13 / `loop_budget` 12 — the stop hook will decline to continue at end of this turn on budget grounds regardless of ISSUE_002.

---
*Updated: 2026-04-19T22:45:00Z*
