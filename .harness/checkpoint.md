# Harness Checkpoint

## Last Completed
**unit_017 (PHASE_004):** Mirrored the parallel-validation-layer rule into [templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) section 10 (Validate) as a **`Parallel Layer 1 + Layer 2 (when enabled).`** bold-label paragraph.

- Semantically identical to the command-doc version landed in unit_016 — same trigger (`config.agent_delegation.parallel_validation_layers == true`), same **single-assistant-message with multiple `Bash` tool calls** shape, same all-must-pass failure semantics with no Layer 3/4 advancement on red, same **Layers 3 and 4 stay serial** rule with the same port/fixture/DB/test-account justification, same flag-off default preservation.
- Compressed to match the template's compact-section style (no heading-level sub-section; single bold-label paragraph inline with the Validate section's other prose).

## What Failed (if anything)
None.

## What Is Next
**Complete unit_018 (PHASE_004):** Update evidence-recording format in **both** invoke docs to include **per-layer timing** (e.g., `"pnpm lint exits 0 (2.1s)"`). Goes into [commands/invoke.md](skills/development-harness/commands/invoke.md) Step 9's "On Success" block and [workspace-commands template](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) section 10's "On success" block. Rationale: with parallel Layer 1 + Layer 2, wall-clock drops from `t_layer1 + t_layer2` to `max(t_layer1, t_layer2)`; per-layer timing makes that benefit visible in checkpoint history. This closes PHASE_004.

## Blocked By
None.

## Evidence
- [skills/development-harness/templates/workspace-commands/invoke-development-harness.md:114](skills/development-harness/templates/workspace-commands/invoke-development-harness.md#L114): new **Parallel Layer 1 + Layer 2** paragraph in section 10.
- Grep: `Parallel Layer 1` + `config.agent_delegation.parallel_validation_layers` + `single assistant message` + `unchanged from v1` all present in section 10.
- Cross-doc consistency confirmed: both docs cite the same flag name, the same fan-out shape, the same all-must-pass semantics, the same Layers-3/4-stay-serial rule, and the same flag-off default.
- `python -m unittest discover skills/development-harness/scripts/tests` → 109/109 pass (docs-only change).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; this session continues under `/loop /invoke-development-harness`. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_004 PR opens after unit_018 — the next unit will close the phase.
- **Branch:** `feat/phase-004-parallel-validation-layers`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 17 / `loop_budget` 12 — `/loop` remains the driver. Budget knob gets revisited under `unit_bugfix_002` / PHASE_011 doc pass.

---
*Updated: 2026-04-20T00:00:00Z*
