# PHASE_006: Orchestrator Agent Contract

## Objective
Define the sub-agent's job, tool allowlist, hard rules, and structured report schema so that orchestration is a verifiable contract rather than free-form delegation.

## Why This Phase Exists
In the parallel model, the main agent (orchestrator) fans out work to sub-agents via `Agent(subagent_type: "harness-unit")`. Without a crisp contract the sub-agents can drift: touching `.harness/`, pushing branches, returning unstructured prose. A dedicated agent definition plus reinforced core rules lock down the contract and make the scope-violation check enforceable.

## Scope
- New `skills/development-harness/templates/claude-code/agents/harness-unit.md`:
  - System prompt: "Execute exactly one harness unit inside an isolated worktree following the unit contract and emit the structured report."
  - Tool allowlist: Read, Edit, Write, Glob, Grep, Bash (restricted: no `git push`, no `git merge`, no writes outside the worktree, no writes to `.harness/`).
  - Hard rules baked into the prompt: only commit on the pre-created branch; never rebase; read `.harness/WORKTREE_UNIT.json` for identity; emit the final report as structured JSON.
  - Report schema baked in:
    ```
    {
      "unit_id": "…",
      "status": "succeeded" | "failed",
      "validation_evidence": ["…"],
      "commits": ["<sha>", …],
      "touched_paths_actual": ["…"],
      "failure": null | {"category": "validation" | "scope_violation" | "ambiguity", "detail": "…"}
    }
    ```
- Update `skills/development-harness/templates/claude-code/rules/harness-core.md` with orchestrator-vs-sub-agent boundary rules:
  - Only the orchestrator modifies `.harness/` or runs `git merge`.
  - Sub-agents commit only within their worktree branch; never push, never rebase.
  - A worktree containing `.harness/WORKTREE_UNIT.json` is a fan-out environment; follow the harness-unit contract exactly.
- Mirror the rule additions in `skills/development-harness/templates/rules/harness-core.mdc` for Cursor.

> ⚠️ **Edit target:** `skills/development-harness/**` only.

## Non-goals
- Writing the code path that dispatches `Agent(harness-unit)` — that is PHASE_007's invoke rewrite.
- Cursor-specific agent definition support (Cursor doesn't have an analogous agent system; the rules-level constraints are the Cursor equivalent for now).

## Dependencies
None strictly; ordered alongside PHASE_005 since PHASE_007 consumes both.

## User-visible Outcomes
- Reading the agent definition, a sub-agent knows exactly what it can and cannot touch and what it must return.
- The core rule file makes the orchestrator-vs-sub-agent boundary explicit.

## Units of Work

| ID | Description | Acceptance Criteria | Validation Method | Status |
|----|-------------|--------------------|--------------------|--------|
| unit_026 | New `templates/claude-code/agents/harness-unit.md` with system prompt, tool allowlist, report schema | File exists; frontmatter + prompt + allowlist + report schema all present; prompt references `.harness/WORKTREE_UNIT.json` | self-review checklist + grep | pending |
| unit_027 | Update `templates/claude-code/rules/harness-core.md` with orchestrator/sub-agent boundary | All three rule bullets present (orchestrator-only merges, sub-agent no-push/no-rebase, WORKTREE_UNIT.json = fan-out env) | grep for each bullet | pending |
| unit_028 | Mirror in `templates/rules/harness-core.mdc` (Cursor) | Same three rule bullets present with wording adjusted for `.mdc` frontmatter | grep | pending |

## Validation Gates
- **Layer 1:** Markdown files parse; frontmatter valid.
- **Layer 2:** Self-review: the agent definition is self-contained (a fresh sub-agent with only the briefing can execute the contract).

## Deployment Implications
Not deploy-affecting.

## Completion Evidence Required
- `templates/claude-code/agents/harness-unit.md` exists.
- Grep confirms all three core-rule additions in both rule files.
- Agent definition passes a dry-read: the report schema and tool allowlist are unambiguous.

## Rollback / Failure Considerations
Docs-only. `git revert` on failure.

## Status
pending
