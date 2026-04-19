# Harness Checkpoint

## Last Completed
**unit_027 (PHASE_006):** Orchestrator-vs-sub-agent boundary now baked into the Claude Code core rules so every session knows which role it's playing.

- Appended `## Orchestrator vs sub-agent boundary` to [templates/claude-code/rules/harness-core.md](skills/development-harness/templates/claude-code/rules/harness-core.md) below the existing Delegation section.
- **Three bullets verbatim in the phase-doc order:**
  1. **Only the orchestrator modifies `.harness/` or runs `git merge`.** Orchestrator defined as the main agent running `/invoke-development-harness`. Sub-agents (via `Agent(subagent_type: "harness-unit")`) treat `.harness/` as read-only; fan-in merges are gated by the scope-violation check (unit_022) and the `.harness/.lock` mutex (unit_023).
  2. **Sub-agents commit only within their worktree branch; never `git push`, never `git rebase`, never `git reset --hard`.** Branch is the pre-created `harness/<batch_id>/<unit_id>`; orchestrator owns any history rewrite.
  3. **A worktree containing `.harness/WORKTREE_UNIT.json` is a fan-out environment.** Sentinel detection tells the agent which contract to follow (the `harness-unit` template landed in unit_026). Explicitly covers the sentinel-absent case too — that's the orchestrator or an ordinary session, and the harness-unit contract does not apply.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_028 (PHASE_006):** Mirror the same three boundary bullets into [templates/rules/harness-core.mdc](skills/development-harness/templates/rules/harness-core.mdc) (Cursor). Cursor doesn't have a native `Agent` primitive analogous to Claude Code's, so the **rules-level constraint IS the Cursor equivalent** for orchestrator/sub-agent boundary enforcement — a Cursor user with multiple concurrent sessions is expected to read these rules and behave accordingly. After 028 lands, PHASE_006 closes and the PR opens.

## Blocked By
None.

## Evidence
- [skills/development-harness/templates/claude-code/rules/harness-core.md:33-36](skills/development-harness/templates/claude-code/rules/harness-core.md#L33-L36): new section with three bullets.
- Grep: `Only the orchestrator` (line 34), `Sub-agents commit only` (line 35), `fan-out environment` (line 36) — all three acceptance bullets present.
- `python -m unittest discover skills/development-harness/scripts/tests` → 171/171 pass (docs-only change; test suite unchanged).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; this session continues under `/loop /invoke-development-harness`. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_006 PR opens after unit_028 (next unit closes the phase).
- **Branch:** `feat/phase-006-orchestrator-contract`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 27 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_006 progress: **2/3 units done** (026 agent template, 027 Claude Code boundary rules). Remaining: 028 Cursor mirror — closes the phase.
- Test-suite count unchanged at 171 across PHASE_006 (docs-only phase).

---
*Updated: 2026-04-20T03:40:00Z*
