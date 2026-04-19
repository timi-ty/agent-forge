# PHASE_001: Schema and Data Model

## Objective
Extend the harness data model — phase-graph, state, config, manifest — with the fields required to express unit-level dependencies, blast radius, parallelism policy, and fleet runtime state. This is the foundational breaking change on which every later phase depends.

## Why This Phase Exists
The current harness cannot express what it needs to for parallel execution: there is no unit-level `depends_on`, no `touches_paths`, no fleet state, no parallelism config. Without these fields the invoke command cannot select a batch, the merger cannot verify blast radius, and the stop hook cannot reason about in-flight work. Every later phase assumes these fields exist.

## Scope
- Extend `skills/development-harness/schemas/phase-graph.json` — add `depends_on` (required on every unit), `touches_paths` (required when `parallel_safe: true`), and `parallel_safe` on units, with illustrative example data.
- Extend `skills/development-harness/schemas/state.json` — add `execution.fleet` block (`mode`, `batch_id`, per-unit fleet entries with worktree path, branch, status, conflict metadata, agent summary path).
- Extend `skills/development-harness/schemas/config.json` — add `execution_mode.parallelism` (`enabled`, `max_concurrent_units`, `conflict_strategy`, `require_touches_paths`, `allow_cross_phase`), `execution_mode.agent_delegation` (`use_explore_for_research`, `use_code_review_skill_for_phase_review`, `parallel_validation_layers`), and `execution_mode.versioning` (`break_on_schema_bump`).
- Extend `skills/development-harness/schemas/manifest.json` and the `.gitignore` template — register `.harness/worktrees/` and `.harness/logs/` as harness-owned transient directories.
- Bump `SCHEMA_VERSION` in `skills/development-harness/scripts/harness_utils.py` from `"1.0"` to `"2.0"`; update `check_schema_version` to emit the actionable "re-run `/create-development-harness`" error.
- Extend `skills/development-harness/scripts/validate_harness.py` with required-field enforcement, `depends_on` cycle detection, `touches_paths` path-safety checks (rejecting `..` and absolute paths), `fleet.mode` enum check, and a version gate that rejects `schema_version: "1.0"` with the re-create message.

> ⚠️ **Edit target:** all changes in this phase land in `skills/development-harness/**`. The running harness in `.harness/scripts/` is a frozen copy made at bootstrap time; leave it alone. If `.harness/` becomes inconsistent mid-roadmap, `/clear` + `/create` re-bootstraps from the updated skill source.

## Non-goals
- Any consumer of the new fields (frontier selector, batcher, dispatch, merge) — those are PHASE_002 and PHASE_005.
- Any migration code for existing v1 harnesses — explicitly no migration is provided. Validator rejects v1 with a re-create pointer.
- Any changes to invoke flow behavior — that is PHASE_007.

## Dependencies
None.

## User-visible Outcomes
- `validate_harness.py` on a fresh v2 harness passes.
- `validate_harness.py` on a v1 fixture exits non-zero with a clear "re-run `/create-development-harness`" message.
- Harness authors can declare unit-level dependencies and blast radius in their phase plans.

## Units of Work

| ID | Description | Acceptance Criteria | Validation Method | Status |
|----|-------------|--------------------|--------------------|--------|
| unit_001 | Extend `schemas/phase-graph.json` with required `depends_on`, `touches_paths` (required when `parallel_safe: true`), `parallel_safe` on units; example data updated | Example phase-graph contains all new fields; `touches_paths` values use repo-relative glob syntax; example passes the updated validator | `python -m unittest skills.development-harness.scripts.tests.test_validate_harness` | pending |
| unit_002 | Extend `schemas/state.json` with `execution.fleet` block | `fleet.mode` enum (`idle`/`dispatched`/`merging`); per-unit entries carry worktree path, branch, status, conflict, agent summary path; example validates | `python -m unittest skills.development-harness.scripts.tests.test_validate_harness` | pending |
| unit_003 | Extend `schemas/config.json` with `execution_mode.parallelism`, `execution_mode.agent_delegation`, `execution_mode.versioning` | All three subsections present with default values; `versioning.break_on_schema_bump` defaults `true` | `python -m unittest skills.development-harness.scripts.tests.test_validate_harness` | pending |
| unit_004 | Register `.harness/worktrees/` and `.harness/logs/` in `schemas/manifest.json` and `.gitignore` template | Both paths in manifest as harness-owned directories; `.gitignore` template contains both entries | `python -m unittest skills.development-harness.scripts.tests.test_validate_harness` | pending |
| unit_005 | Bump `SCHEMA_VERSION` in `scripts/harness_utils.py` 1.0→2.0; `check_schema_version` emits re-create error on mismatch | Module-level constant is `"2.0"`; `check_schema_version("1.0")` raises/returns error mentioning `/create-development-harness` | `python -m unittest skills.development-harness.scripts.tests.test_harness_utils` | pending |
| unit_006 | Extend `validate_harness.py` with required-field enforcement, `depends_on` cycle detection, path-safety checks, version gate | Validator rejects v1 fixture with re-create message; rejects missing `depends_on`; rejects `parallel_safe: true` without `touches_paths`; rejects `..` and absolute paths; detects cycles | `python -m unittest skills.development-harness.scripts.tests.test_validate_harness` (new cases incl. v1 fixture) | pending |

## Validation Gates
Validation hierarchy layers 1 and 2 apply:
- **Layer 1 (Static checks):** Python syntax valid; JSON schemas parse.
- **Layer 2 (Unit tests):** `test_validate_harness.py` and `test_harness_utils.py` pass including new cases.

## Deployment Implications
Not deploy-affecting. This phase modifies skill source code distributed via `install.sh`/`sync-skills`; there is no runtime deployment target.

## Completion Evidence Required
- `python -m unittest skills.development-harness.scripts.tests.test_validate_harness` exits 0 with all new cases green.
- `python -m unittest skills.development-harness.scripts.tests.test_harness_utils` exits 0.
- Grep: `SCHEMA_VERSION = "2.0"` in `skills/development-harness/scripts/harness_utils.py`.
- Each unit's validation evidence recorded in `.harness/phase-graph.json`.

## Rollback / Failure Considerations
If a schema change breaks the validator on the in-workspace `.harness/` state: this phase modifies `skills/**`, not `.harness/**`. The running harness keeps using the frozen v1 copy in `.harness/scripts/` and remains operational. To roll back, `git revert` the phase commits in `skills/development-harness/**`.

If `harness_utils.py` changes accidentally break the skill scripts themselves: unit tests on the SKILL copy (`skills/development-harness/scripts/tests/`) would catch this before commit. If caught post-commit, revert the commit.

## Status
pending
