# PHASE_012: Release Readiness

## Objective
Make the v2 schema bump safe to adopt by ensuring users see a clear, actionable message when they encounter a version mismatch — no silent migration, no ambiguous failure.

## Why This Phase Exists
Per roadmap direction, no migration code is provided. That makes explicit version-mismatch messaging the entire user-visible upgrade path. If a user updates the skill without re-creating their harness, the only acceptable behavior is to reject the stale harness with a pointer to `/create-development-harness`.

## Scope
- Add a parallelism readiness checklist to `skills/development-harness/references/parallel-execution.md`:
  - `touches_paths` declared on every parallelism-eligible unit.
  - No pending unit modifies a shared aggregator file (e.g., a central router, a single `index.ts` re-exporter).
  - CI can handle multi-commit pushes (no per-commit hooks that break on rapid-fire commits).
- Add a "Version upgrades" note to `skills/development-harness/SKILL.md`: re-run `/create-development-harness` when `schema_version` changes; `ROADMAP.md` and `PHASES/*.md` are untouched by the recreate flow; no migration script is provided by design.
- Update `skills/development-harness/commands/update.md` and `skills/development-harness/templates/workspace-commands/update-development-harness.md`: detect `schema_version` mismatch between the installed `.harness/` and the installed skill; emit a pointer to `/create-development-harness` with a one-line explanation; do not attempt auto-migration.
- Test coverage: `test_validate_harness.py` already rejects v1 fixtures with the re-create message (PHASE_001 unit_006); re-assert here with a dedicated test fixture simulating the user flow.

> ⚠️ **Edit target:** `skills/development-harness/**` only.

## Non-goals
- A migration script in any form.
- Automatic migration hints inferred from the v1 data shape.

## Dependencies
- PHASE_001 (`validate_harness.py` version gate; `versioning.break_on_schema_bump` config field).

## User-visible Outcomes
- A user running `/update-development-harness` on a v1-era harness sees a clear instruction to re-create.
- `references/parallel-execution.md` contains an actionable readiness checklist.
- `SKILL.md` documents the upgrade path.

## Units of Work

| ID | Description | Acceptance Criteria | Validation Method | Status |
|----|-------------|--------------------|--------------------|--------|
| unit_051 | Parallelism readiness checklist in `references/parallel-execution.md` | Section present; all three bullets with rationale | grep | pending |
| unit_052 | "Version upgrades" note in `SKILL.md` | Paragraph present; explicitly states "no migration script is provided by design" and points to `/create-development-harness` | grep | pending |
| unit_053 | Update `/update-development-harness` (command + workspace template) to detect mismatch and emit re-create pointer; verify with v1 fixture | Both docs instruct the mismatch detection + pointer behavior; v1 fixture test asserts the message is emitted | `python -m unittest skills.development-harness.scripts.tests.test_update_command` + grep | pending |

## Validation Gates
- **Layer 1:** Markdown parses.
- **Layer 2:** `test_update_command` passes.

## Deployment Implications
Not deploy-affecting.

## Completion Evidence Required
- All greps succeed.
- `test_update_command` exits 0.

## Rollback / Failure Considerations
Docs + command logic only. Revert on failure.

## Status
pending
