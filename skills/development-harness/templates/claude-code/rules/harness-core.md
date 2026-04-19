---
description: Core development harness operational rules
paths:
  - "**/*"
---

# Development Harness Core Rules

## Harness State
- Before modifying any harness file (.harness/*, PHASES/*), read .harness/ARCHITECTURE.md
- The authoritative source for "what to do next" is .harness/phase-graph.json via select_next_unit.py
- state.json is a runtime snapshot; phase-graph.json is canonical for phase/unit truth
- checkpoint.md is human-readable summary -- do not treat it as authoritative data

## Ownership
- Files with harness- prefix in .claude/rules/ are harness-owned
- Files in .harness/ and PHASES/ are harness-owned
- ROADMAP.md and all application source code are product-owned -- never modify without explicit user approval
- Check .harness/manifest.json before modifying any file to verify ownership

## Quality
- Run validation (linter, tests) after every code change
- Never mark a unit complete without validation evidence recorded in phase-graph.json
- Never mark a deploy-affecting phase complete without deployment verification

## Delegation (when to dispatch sub-agents)
- **Default to inline.** Most units are a few files plus a test run in the main context; spawning sub-agents has a round-trip cost that only pays off above defined thresholds.
- **Dispatch `Agent(Explore)` before planning** when the unit description contains `refactor`, `extend`, `fix`, `migrate`, or `update` — the main context plans from the Explore report instead of re-reading files itself. See `commands/invoke.md` Step 6 for the prompt template.
- **Fan out 2–3 `Agent(general-purpose)` calls in one assistant message** when the plan touches ≥4 independent files with no read-after-write ordering (e.g., mirrored template edits). Below 4 files, edit inline. See `commands/invoke.md` Step 8.
- **Dispatch `code-review` + `commit-agent-changes` concurrently** at phase completion when both skills are installed — one reads the branch diff, the other commits and opens or updates the PR. If only one is installed, fall back to serial. See `commands/invoke.md` Step 10.
- **Stay inline** for any read-after-write sequence (rename + callsite updates, schema edit + consumer sync), any unit below the thresholds above, and anything ambiguous — the main agent can always choose not to fan out.

## Orchestrator vs sub-agent boundary
- **Only the orchestrator modifies `.harness/` or runs `git merge`.** The orchestrator is the main agent running `/invoke-development-harness`. Sub-agents dispatched via `Agent(subagent_type: "harness-unit")` treat `.harness/` as read-only and never invoke `git merge` — fan-in is the orchestrator's job alone, gated by the scope-violation check and the `.harness/.lock` mutex.
- **Sub-agents commit only within their worktree branch; never `git push`, never `git rebase`, never `git reset --hard`.** A `harness-unit` sub-agent was dispatched onto a pre-created `harness/<batch_id>/<unit_id>` branch inside an isolated worktree; it commits there and returns. The orchestrator is responsible for pushing, rebasing, or rewriting any history.
- **A worktree containing `.harness/WORKTREE_UNIT.json` is a fan-out environment.** If you find that sentinel in the worktree root you are running as the `harness-unit` sub-agent — follow `templates/claude-code/agents/harness-unit.md` exactly (read the sentinel for identity, obey the tool allowlist, emit the required JSON report). If the sentinel is absent you are the orchestrator or an ordinary session; the harness-unit contract does not apply.
