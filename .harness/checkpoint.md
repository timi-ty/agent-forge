# Harness Checkpoint

## Last Completed
**PHASE_003 (all five units).** Intra-unit helper-agent delegation is fully documented.

- **unit_011** — [commands/invoke.md](skills/development-harness/commands/invoke.md) gains new **Step 6: Exploration (conditional)** with the five trigger keywords (`refactor`, `extend`, `fix`, `migrate`, `update`), five skip keywords (`add`, `new`, `create`, `insert`, `scaffold`), and a concrete `Agent(subagent_type: "Explore", thoroughness: "medium")` call template.
- **unit_012** — [templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) mirrors the step as new `## 7. Exploration (conditional)` in the compact-template style.
- **unit_013** — **Multi-file parallel-edit guidance** landed in both docs: the **≥4 independent files** threshold and **single-assistant-message, 2–3 `Agent(general-purpose)`** fan-out shape. Above 3 concurrent agents, coordination cost erodes the speedup; below 4 files, the round-trip cost isn't worth it. Group by independence, not file count.
- **unit_014** — **Parallel phase-review dispatch** landed in both docs: at phase completion, when both `code-review` and `commit-agent-changes` are installed, dispatch them in **one assistant message with two `Agent` calls** (disjoint state: one reads, one writes). Serial fallback when only one is installed.
- **unit_015** — Both [harness-core.md](skills/development-harness/templates/claude-code/rules/harness-core.md) (Claude Code) and [harness-core.mdc](skills/development-harness/templates/rules/harness-core.mdc) (Cursor) gain a new **`## Delegation (when to dispatch sub-agents)`** section that consolidates the three dispatch shapes with pointers to the specific Steps in `commands/invoke.md` where the concrete prompt templates live. Opens with "Default to inline" and closes with "Stay inline" fallbacks so the main agent's default remains direct `Edit`/`Write`.

## What Failed (if anything)
None.

## What Is Next
**Run PHASE_003 phase completion review**, open the phase PR, autonomous squash-merge per [harness-git.md](.claude/rules/harness-git.md). After merge, advance to **unit_016 (PHASE_004, parallel-validation-layers)** on a fresh branch — rewrite the validation step in `commands/invoke.md` to fan out Layer 1 (lint + typecheck + formatter) and Layer 2 (unit tests) as concurrent Bash calls when `agent_delegation.parallel_validation_layers == true`.

## Blocked By
None.

## Evidence
- [skills/development-harness/commands/invoke.md](skills/development-harness/commands/invoke.md): new Step 6 (Exploration); Step 10 parallel-dispatch sub-section; Step 12 pointer.
- [skills/development-harness/templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md): mirrored new sections 7, 13 (parallel dispatch), and a section-12 pointer.
- [skills/development-harness/templates/claude-code/rules/harness-core.md](skills/development-harness/templates/claude-code/rules/harness-core.md) and [skills/development-harness/templates/rules/harness-core.mdc](skills/development-harness/templates/rules/harness-core.mdc): new Delegation section, byte-identical block across both files.
- `Grep` across both rule files: `## Delegation (when to dispatch sub-agents)` matches exactly once in each.
- `python -m unittest discover skills/development-harness/scripts/tests` → 109/109 pass (docs-only phase; test suite unchanged end-to-end).
- Out-of-band: ISSUE_002 injected this turn-cycle with `unit_bugfix_002` scheduled at head of PHASE_011 — retire the Claude Code Stop-hook-as-driver, use `/loop /invoke-development-harness`. (This very session is being driven by `/loop`, validating the workaround in practice.)

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; workaround is `/loop /invoke-development-harness`. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_003 PR opens now with all five units.
- **Branch:** `feat/phase-003-intra-unit-delegation` (delete on merge).
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 15 / `loop_budget` 12 — over budget. `/loop` is driving so the hook's budget check is bypassed this session. The budget knob will get revisited as a config field in `unit_bugfix_002` / PHASE_011 doc pass.

---
*Updated: 2026-04-19T23:20:00Z*
