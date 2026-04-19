# Harness Checkpoint

## Last Completed
**unit_014 (PHASE_003):** Parallel phase-review dispatch guidance landed in **both** invoke docs.

- [commands/invoke.md](skills/development-harness/commands/invoke.md) Step 10 (Phase Completion Review) gains a new sub-section at the top — **"Parallel dispatch with commit-agent-changes"**. When both skills are installed, dispatch them in a **single assistant message** containing **two `Agent(subagent_type: "general-purpose")` tool calls**: one runs `code-review` read-only on the branch diff, the other runs `commit-agent-changes` to commit, push, and open or update the PR. Disjoint state (read vs. write non-overlapping files) means they cannot conflict. If only one skill is installed, fall back to serial.
- [commands/invoke.md](skills/development-harness/commands/invoke.md) Step 12 (Commit) gains a call-out pointer: at phase completion, skip the separate delegation below if Step 10 already fan-out the work in parallel.
- [templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) section 13 carries the same rule as a **`Parallel dispatch.`** bold-label paragraph; section 12 gains the same Step-12-skip pointer.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_015 (PHASE_003):** Update [skills/development-harness/templates/claude-code/rules/harness-core.md](skills/development-harness/templates/claude-code/rules/harness-core.md) and the Cursor mirror [skills/development-harness/templates/rules/harness-core.mdc](skills/development-harness/templates/rules/harness-core.mdc) with **delegate-vs-inline guidance** — when to dispatch an `Explore` agent (modifying existing systems), when to fan out 2–3 `general-purpose` agents (≥4 independent file edits), when to dispatch `code-review` + `commit-agent-changes` in parallel (phase completion, both skills installed), and when to run inline in the main context (everything else, especially read-after-write sequences).

## Blocked By
None.

## Evidence
- [skills/development-harness/commands/invoke.md:224-251](skills/development-harness/commands/invoke.md#L224-L251): Parallel dispatch sub-section with concrete two-Agent-call code sample and disjoint-state justification.
- [skills/development-harness/commands/invoke.md:323](skills/development-harness/commands/invoke.md#L323): Step 12 pointer back to Step 10's parallel-dispatch call-out.
- [skills/development-harness/templates/workspace-commands/invoke-development-harness.md:152](skills/development-harness/templates/workspace-commands/invoke-development-harness.md#L152): compressed "Parallel dispatch." paragraph in section 13.
- [skills/development-harness/templates/workspace-commands/invoke-development-harness.md:139](skills/development-harness/templates/workspace-commands/invoke-development-harness.md#L139): section 12 pointer.
- Grep: both docs carry "Parallel dispatch" heading, "single assistant message", and "two `Agent` tool calls" at phase completion.
- `python -m unittest discover skills/development-harness/scripts/tests` → 109/109 pass (docs-only change).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Stop-hook portability on Windows when only `python` is on PATH. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot. This session is currently being driven by `/loop /invoke-development-harness` — exactly the workaround ISSUE_002 recommends. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_003 PR opens after unit_015.
- **Branch:** `feat/phase-003-intra-unit-delegation`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 14 / `loop_budget` 12 — over budget, but `/loop` is driving so the hook's budget check is bypassed this session.

---
*Updated: 2026-04-19T23:00:00Z*
