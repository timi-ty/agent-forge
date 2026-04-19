# PHASE_003: Intra-Unit Helper-Agent Delegation

## Objective
Adopt multi-agent workflows inside a single unit of work — before any worktree infrastructure lands. Applies to both the current single-unit flow and the future batched flow, giving an immediate speed win with zero new scripts.

## Why This Phase Exists
The existing invoke command does all exploration, implementation, and review serially in the main agent's context. A lot of that work is parallelizable inside one unit: exploration (Explore agent), multi-file independent edits (fan-out general-purpose agents), and phase-completion review (code-review skill concurrent with commit-agent-changes). Capturing this guidance in the invoke command documentation is a pure instruction change — no code, no state changes, no risk to the execution model.

## Scope
- Insert an Exploration step in `skills/development-harness/commands/invoke.md`: when the selected unit's description implies modifying existing systems (keywords: refactor, extend, fix, migrate, update), dispatch `Agent(subagent_type: "Explore", thoroughness: "medium")` before implementation. Use the findings to inform the plan.
- Mirror the Exploration step in `skills/development-harness/templates/workspace-commands/invoke-development-harness.md`.
- Add multi-file parallel-edit guidance to both invoke docs: when the implementation plan touches ≥4 independent files, fan out to 2–3 `Agent(general-purpose)` calls in one assistant message. Only when edits are truly independent.
- Add parallel phase-review dispatch guidance: during phase completion review (Step 9), when the `code-review` skill is installed, dispatch it via `Agent` concurrently with the `commit-agent-changes` commit/PR prep.
- Update `skills/development-harness/templates/claude-code/rules/harness-core.md` (and the Cursor mirror `templates/rules/harness-core.mdc`) with guidance on when to delegate vs. handle inline.

> ⚠️ **Edit target:** `skills/development-harness/**` only. Instructions in the running `.harness/` copy do not change here.

## Non-goals
- Worktree infrastructure — PHASE_005.
- Any state-script changes — none.
- Parallel validation layers — PHASE_004 covers that independently.

## Dependencies
None. Pure instructions.

## User-visible Outcomes
- Reading the updated invoke command, an agent understands when to fan out to sub-agents inside one unit.
- Phase completion review runs code-review in parallel with commit prep, cutting wall-clock.

## Units of Work

| ID | Description | Acceptance Criteria | Validation Method | Status |
|----|-------------|--------------------|--------------------|--------|
| unit_011 | Insert Exploration step in `commands/invoke.md` | New step documented; lists trigger keywords; example `Agent(Explore)` call shown | self-review checklist + grep for step marker | pending |
| unit_012 | Mirror Exploration step in `templates/workspace-commands/invoke-development-harness.md` | New step present and consistent with the command doc | self-review + grep | pending |
| unit_013 | Multi-file parallel-edit guidance in both docs | Rule states threshold (≥4 independent files) and fan-out shape (single assistant message, 2–3 calls) | self-review + grep | pending |
| unit_014 | Parallel phase-review dispatch guidance in both docs | Rule states code-review and commit-agent-changes run in one assistant message when both are installed | self-review + grep | pending |
| unit_015 | Update `harness-core.md` (Claude Code) and `harness-core.mdc` (Cursor) with delegate-vs-inline guidance | Both files contain the new guidance block; wording consistent | self-review + grep | pending |

## Validation Gates
- **Layer 1:** All edited files parse (markdown frontmatter intact).
- **Layer 2:** No test code added. Self-consistency check: the instructions correctly distinguish "parallel" (single message, multiple tool calls) from "sequential" dispatch.

## Deployment Implications
Not deploy-affecting.

## Completion Evidence Required
- Grep finds the new Exploration step in both files.
- Grep finds the multi-file fan-out rule in both files.
- Grep finds the parallel phase-review rule in both files.
- Grep finds the delegate-vs-inline block in both `harness-core` files.

## Rollback / Failure Considerations
Docs-only. Any issue is a straight `git revert`.

## Status
pending
