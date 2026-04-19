# Harness Checkpoint

## Last Completed
**PHASE_006 complete (all 3 units).** The orchestrator/sub-agent contract is now explicit on both Claude Code (with a native agent template) and Cursor (with a rules-level framing that acknowledges the lack of a native Agent primitive).

- **unit_026** — New [templates/claude-code/agents/harness-unit.md](skills/development-harness/templates/claude-code/agents/harness-unit.md) (~170 LOC). First Claude-Code-native agent template shipped by the skill. Frontmatter wires `name: harness-unit` + `tools: [Read, Edit, Write, Glob, Grep, Bash]`. System prompt: Identity (read `WORKTREE_UNIT.json`), Tool allowlist (hard forbidden list: `git push`/`merge`/`rebase`/`reset --hard`/`checkout -b`/`worktree add/remove`, no `.harness/` edits, no writes outside the worktree), Workflow, JSON report schema (baked in verbatim), three worked report examples.
- **unit_027** — Appended `## Orchestrator vs sub-agent boundary` to [templates/claude-code/rules/harness-core.md](skills/development-harness/templates/claude-code/rules/harness-core.md) with the three phase-doc bullets. Each bullet names its concrete enforcement (scope-violation check + `.harness/.lock` mutex; pre-created branch; sentinel-based self-identification).
- **unit_028** — Mirrored to [templates/rules/harness-core.mdc](skills/development-harness/templates/rules/harness-core.mdc) with a Cursor-specific preamble ("Cursor does not have a native agent-dispatch primitive; these rules therefore describe the contract for a human operator or a second Cursor session…"). Same three bullets adapted for Cursor's session model. The JSON report format from the Claude Code agent template is documented as **tool-agnostic** so Cursor sub-agent sessions emit the same structure.

**Cross-doc consistency verified via `diff`:** the only deltas between the Claude Code and Cursor rule files are (a) the pre-existing frontmatter delimiter (`paths:` vs `globs:`), (b) the pre-existing rules-directory path (`.claude/rules/` vs `.cursor/rules/`), and (c) the three new boundary bullets with their expected tool-specific wording.

## What Failed (if anything)
None.

## What Is Next
**Run PHASE_006 phase completion review**, open the phase PR, autonomous squash-merge per [harness-git.md](.claude/rules/harness-git.md). After merge, advance to **unit_029 (PHASE_007, invoke-command-rewrite)** — rewrite `commands/invoke.md` into a single batch-driven flow where batch-of-1 runs in-tree (current behavior) and batch-of-N fans out via `Agent(subagent_type: "harness-unit")`. PHASE_007 consumes everything from PHASE_005 (dispatch/merge/teardown/scope/lock/sync) and PHASE_006 (agent contract) — this is where the parallel-execution substrate first touches the live invoke flow.

## Blocked By
None.

## Evidence
- [templates/claude-code/agents/harness-unit.md](skills/development-harness/templates/claude-code/agents/harness-unit.md): 170 LOC, new file, frontmatter + system prompt.
- [templates/claude-code/rules/harness-core.md](skills/development-harness/templates/claude-code/rules/harness-core.md:33-36): new section, three bullets.
- [templates/rules/harness-core.mdc](skills/development-harness/templates/rules/harness-core.mdc:33-37): mirrored section with preamble + three bullets.
- `diff` between the two rule files — deltas match expected per-tool wording only.
- `python -m unittest discover skills/development-harness/scripts/tests` → **171/171** pass end-to-end (docs-only phase; test suite unchanged).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; this session continues under `/loop /invoke-development-harness`. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_006 PR opens now with all three units.
- **Branch:** `feat/phase-006-orchestrator-contract` (delete on merge).
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 28 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE progress so far: PHASE_001–006 complete (28 units). Remaining: PHASE_007–013 (≈30 units) — starts with the big invoke-command rewrite.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → **171** — held flat across PHASE_006 (docs-only).

---
*Updated: 2026-04-20T03:50:00Z*
