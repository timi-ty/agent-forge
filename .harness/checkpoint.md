# Harness Checkpoint

## Last Completed
**unit_026 (PHASE_006):** New `harness-unit` agent template landed — the first time this skill ships a Claude-Code-native agent definition.

- File: [skills/development-harness/templates/claude-code/agents/harness-unit.md](skills/development-harness/templates/claude-code/agents/harness-unit.md) (~170 lines) under a brand-new `templates/claude-code/agents/` directory.
- **YAML frontmatter:** `name: harness-unit`; one-paragraph `description` (execute one unit inside its dispatched worktree, commit on the pre-created branch, emit the structured JSON report); `tools: [Read, Edit, Write, Glob, Grep, Bash]`.
- **System-prompt body** — five sections:
  1. **Identity** — read `.harness/WORKTREE_UNIT.json` first (carries `batch_id`, `unit_id`, `phase_id`, `touches_paths`). Stop immediately if the file is missing.
  2. **Tool allowlist** — hard rules with an explicit forbidden list: `git push`, `git merge`, `git rebase`, `git reset --hard`, `git checkout -b`, `git worktree add/remove`, writes outside the worktree, writes to `.harness/`.
  3. **Workflow** — read identity → read phase doc → (optional) explore → implement → validate → commit on pre-created branch → emit report.
  4. **Required JSON report** — `unit_id`, `status`, `validation_evidence`, `commits`, `touched_paths_actual`, `failure` (nullable with `category` enum: `validation` | `scope_violation` | `ambiguity` | `infrastructure`). Per-field semantics spelled out.
  5. **Reporting examples** — three worked ones: success, validation failure (after 2 fix attempts), scope-violation realised mid-work.
- Explicit "fail honestly" guidance on scope violations: **don't expand scope silently**; the orchestrator's diff-based check will catch it regardless.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_027 (PHASE_006):** Update [skills/development-harness/templates/claude-code/rules/harness-core.md](skills/development-harness/templates/claude-code/rules/harness-core.md) with three orchestrator-vs-sub-agent boundary rules:
1. Only the **orchestrator** modifies `.harness/` or runs `git merge`.
2. Sub-agents commit only within their worktree branch; **never** push, **never** rebase.
3. A worktree containing `.harness/WORKTREE_UNIT.json` is a fan-out environment — follow the `harness-unit` agent contract exactly.

## Blocked By
None.

## Evidence
- [skills/development-harness/templates/claude-code/agents/harness-unit.md](skills/development-harness/templates/claude-code/agents/harness-unit.md): new 170-line agent definition file.
- Grep verification on acceptance criteria: `name: harness-unit` (line 2), `tools:` block (line 8), `.harness/WORKTREE_UNIT.json` references throughout (lines 21, 23, 25, 40, 48, 49, 59, 90, 166), JSON report schema with exact fields (unit_id, status, validation_evidence, commits, touched_paths_actual, failure), forbidden-tool list.
- `python -m unittest discover skills/development-harness/scripts/tests` → 171/171 pass (docs-only change; test suite unchanged).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; this session continues under `/loop /invoke-development-harness`. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_006 PR opens after unit_028.
- **Branch:** `feat/phase-006-orchestrator-contract`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 26 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_006 progress: **1/3 units done** (026 agent template). Remaining: 027 orchestrator/sub-agent boundary rules in Claude Code's `harness-core.md`, 028 Cursor mirror in `harness-core.mdc`.
- Test-suite count unchanged at 171 (docs-only phase).

---
*Updated: 2026-04-20T03:25:00Z*
