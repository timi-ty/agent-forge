# PHASE_004: Parallel Validation Layers

## Objective
Collapse validation wall-clock by running independent validation layers concurrently when `config.agent_delegation.parallel_validation_layers == true`. Orthogonal to unit-level parallelism.

## Why This Phase Exists
Every unit today runs Layer 1 (lint + typecheck + formatter) and Layer 2 (unit tests) sequentially, even though they share no state. Two Bash calls in one assistant message is the entire change. Layer 3 (integration) and Layer 4 (E2E) remain serial — they commonly contend on ports, fixtures, and DB state.

## Scope
- Rewrite the validation step in `skills/development-harness/commands/invoke.md` so that when the config flag is on, Layer 1 and Layer 2 fan out as concurrent Bash calls in a single assistant message. Collect all exit codes; the unit passes only if every parallel layer passes.
- Mirror the rewrite in `skills/development-harness/templates/workspace-commands/invoke-development-harness.md`.
- Update evidence-recording format in both docs to include per-layer timing (e.g., `"pnpm lint exits 0 (2.1s)"`) so the benefit is visible in checkpoint history.

> ⚠️ **Edit target:** `skills/development-harness/**` only.

## Non-goals
- Parallelism for Layers 3 or 4 — not safe without coordination.
- Changes to the validation hierarchy itself — layers unchanged.
- Any script changes.

## Dependencies
None.

## User-visible Outcomes
- When the flag is on, units that previously took `(lint_time + test_time)` now take `max(lint_time, test_time)`.
- Checkpoint evidence entries show per-layer timing.

## Units of Work

| ID | Description | Acceptance Criteria | Validation Method | Status |
|----|-------------|--------------------|--------------------|--------|
| unit_016 | Rewrite validation step in `commands/invoke.md` to fan out Layer 1 + Layer 2 when the config flag is on | Doc explicitly says "single assistant message, multiple Bash calls"; behavior when flag is off is preserved | self-review checklist + grep for new instruction block | pending |
| unit_017 | Mirror in `templates/workspace-commands/invoke-development-harness.md` | Instruction wording consistent with the command doc | self-review + grep | pending |
| unit_018 | Update evidence-recording format with per-layer timing | Format example present in both docs (e.g., `"pnpm lint exits 0 (2.1s)"`) | grep for timing format example | pending |

## Validation Gates
- **Layer 1:** Markdown parses; frontmatter intact.
- **Layer 2:** Self-consistency check on the instruction.

## Deployment Implications
Not deploy-affecting.

## Completion Evidence Required
- Grep finds the parallel-layer instruction block in both docs.
- Grep finds the per-layer timing format example in both docs.

## Rollback / Failure Considerations
Docs-only. `git revert` on failure.

## Status
pending
