# Harness Checkpoint

## Last Completed
**unit_016 (PHASE_004):** Parallel validation-layer guidance landed in [commands/invoke.md](skills/development-harness/commands/invoke.md) Step 9 (Validate).

- New sub-section `### Parallel Layer 1 + Layer 2 (when enabled)` at the top of Step 9, before the existing Layer 1 / Layer 2 / Layer 3 / Layer 4 subsections.
- Trigger: `config.agent_delegation.parallel_validation_layers == true`.
- Shape: **single assistant message with multiple `Bash` tool calls** for lint, typecheck, and unit tests. Concrete three-call sample included.
- Failure semantics: the unit passes only if **every** parallel call exits 0. Any failure falls into the existing On Failure flow below; **no** Layer 3 or Layer 4 advancement on red.
- Layers 3 and 4 **stay serial** (integration + E2E commonly contend on ports, fixtures, databases, test accounts).
- Flag-off branch is the default and is unchanged from the v1 flow — explicit note in the sub-section: "The flag-off behavior is unchanged from the v1 flow."

## What Failed (if anything)
None.

## What Is Next
**Complete unit_017 (PHASE_004):** Mirror the parallel-validation-layer sub-section in [templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) section 10 (Validate). Wording should be consistent with the command-doc version — same trigger, same single-assistant-message shape, same failure semantics, same Layer-3/4-stay-serial rule, same flag-off default.

## Blocked By
None.

## Evidence
- [skills/development-harness/commands/invoke.md:181-197](skills/development-harness/commands/invoke.md#L181-L197): new Parallel Layer 1 + Layer 2 sub-section.
- Grep: section header at line 181; trigger flag `config.agent_delegation.parallel_validation_layers` at line 183; "single assistant message" at line 183; "The flag-off behavior is unchanged from the v1 flow" present; `Bash(command: ...)` three-call sample included.
- `python -m unittest discover skills/development-harness/scripts/tests` → 109/109 pass (docs-only change).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; this session remains driven by `/loop /invoke-development-harness`. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_004 PR opens after unit_018.
- **Branch:** `feat/phase-004-parallel-validation-layers`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 16 / `loop_budget` 12 — over budget but `/loop` is the driver; the budget knob will get revisited as a config field under `unit_bugfix_002` / PHASE_011 doc pass.

---
*Updated: 2026-04-19T23:45:00Z*
