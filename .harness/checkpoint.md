# Harness Checkpoint

## Last Completed
**PHASE_004 (all three units).** Parallel validation layers documented in both invoke docs.

- **unit_016** — [commands/invoke.md](skills/development-harness/commands/invoke.md) Step 9 gains a `### Parallel Layer 1 + Layer 2 (when enabled)` sub-section at the top. Trigger `config.agent_delegation.parallel_validation_layers == true`; shape is **single assistant message with multiple `Bash` tool calls** for lint + typecheck + unit tests. Concrete three-call sample included. All-must-pass failure semantics; no Layer 3/4 advancement on red. Layers 3 and 4 stay serial (port/fixture/DB/test-account contention). Flag-off default preserved from v1.
- **unit_017** — [workspace-commands template](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) section 10 gains a compact **`Parallel Layer 1 + Layer 2 (when enabled).`** bold-label paragraph — semantically identical to the command-doc version, compressed to the template's single-paragraph style.
- **unit_018** — Evidence-recording format in both docs now requires **per-layer wall-clock timing**. Concrete examples: `"pnpm lint exits 0 (2.1s)"`, `"tsc --noEmit exits 0 (4.8s)"`, `"tests/auth.test.ts passes (5/5, 3.2s)"`. The command doc carries fuller prose on how to source the timing (real from `time`, or the `Ran N tests in X.Xs` tail from unittest) and why it matters (makes the `max(layer_1, layer_2)` benefit visible in checkpoint history over time); the template stays minimal.

## What Failed (if anything)
None.

## What Is Next
**Run PHASE_004 phase completion review**, open the phase PR, autonomous squash-merge per [harness-git.md](.claude/rules/harness-git.md). After merge, advance to **unit_019 (PHASE_005, worktree-dispatch-and-merge-infrastructure)** on a fresh branch — new [skills/development-harness/scripts/dispatch_batch.py](skills/development-harness/scripts/dispatch_batch.py) that creates per-unit git worktrees under `.harness/worktrees/<batch_id>/<unit_id>`, seeds `WORKTREE_UNIT.json`, writes `state.execution.fleet`, with atomic teardown on failure. **This is the first code-bearing phase since PHASE_002**, so the test suite will grow again.

## Blocked By
None.

## Evidence
- [skills/development-harness/commands/invoke.md:181](skills/development-harness/commands/invoke.md#L181): Parallel Layer 1 + Layer 2 sub-section.
- [skills/development-harness/commands/invoke.md:244](skills/development-harness/commands/invoke.md#L244): updated evidence format with per-layer timing examples.
- [skills/development-harness/templates/workspace-commands/invoke-development-harness.md:114](skills/development-harness/templates/workspace-commands/invoke-development-harness.md#L114): mirrored parallel-layer paragraph.
- [skills/development-harness/templates/workspace-commands/invoke-development-harness.md:122](skills/development-harness/templates/workspace-commands/invoke-development-harness.md#L122): updated evidence bullet with per-layer timing examples.
- Grep: `pnpm lint exits 0 \(\d` matches in both files, validating the acceptance criterion.
- `python -m unittest discover skills/development-harness/scripts/tests` → 109/109 pass (docs-only phase end-to-end).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; this session continues under `/loop /invoke-development-harness`. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_004 PR opens now with all three units.
- **Branch:** `feat/phase-004-parallel-validation-layers` (delete on merge).
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 18 / `loop_budget` 12 — `/loop` remains the driver. Budget knob gets revisited under `unit_bugfix_002` / PHASE_011 doc pass.
- PHASE_005 starts code-bearing work after this merge. Expect the test-suite count to climb from 109 again.

---
*Updated: 2026-04-20T00:15:00Z*
