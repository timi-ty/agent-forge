# Harness Checkpoint

## Last Completed
**unit_048 (PHASE_011) — PHASE_011 CLOSED.** [commands/create.md](skills/development-harness/commands/create.md) bootstrap flow extended with Execution Mode questions + parallelism-aware unit authoring.

### Phase 2 additions
New "Execution Mode" category with a **"use exact wording"** preamble and two structured questions:

1. **`Enable parallel unit execution? (y/n, default n)`** → `config.execution_mode.parallelism.enabled`. On `y`, the generated config also carries the four sub-fields (`max_concurrent_units: 3`, `conflict_strategy: "abort_batch"`, `require_touches_paths: true`, `allow_cross_phase: false`) so the generated config is self-documenting. On `y`, the bootstrap agent must point the user at [references/parallel-execution.md](skills/development-harness/references/parallel-execution.md) § "Readiness checklist".

2. **`Break-on-schema-bump vs migrate? (break/migrate, default break)`** → `config.execution_mode.versioning.break_on_schema_bump`. `break → true` (safe default, requires `/create-development-harness` regeneration on schema bump); `migrate → false` (attempts in-place migration — riskier, only with migration tooling reviewed).

### Phase 4 additions
**Step 2 unit-field list** grew from 4 fields to 7:
- `depends_on` (always required, empty list allowed).
- `parallel_safe` with the explicit **"Default to `false` when blast radius is unknown"** guidance (the exact phrase from the acceptance criterion).
- `touches_paths` with "Propose this per unit" instruction + "narrower globs" preference + "required when `parallel_safe: true`" conditional.

**New "Parallelism-by-default" paragraph** below the list: when Phase 2 turned parallelism on, propose `parallel_safe: true` aggressively but verify with the dry-run pipeline `select_next_unit.py --frontier | compute_parallel_batch.py --input - --config .harness/config.json` — `path_overlap_with:*` exclusions are design-time errors. "When in doubt, leave `parallel_safe: false`" is the safety net.

### New regression test
[test_create_bootstrap_parallelism_questions.py](skills/development-harness/scripts/tests/test_create_bootstrap_parallelism_questions.py) — 11 cases in 2 classes:

- **TestPhase2ExecutionModeQuestions (7)** — category heading + both questions verbatim (backtick-quoted) + both config paths + answer-to-value mappings (true/false/break/migrate) + the four parallelism sub-fields + parallel-execution.md + Readiness-checklist cross-link + /create-development-harness recovery path + "use exact wording" preamble.
- **TestPhase4UnitFieldsAddParallelismTriple (4)** — all 3 new fields present + "blast radius" + "Default to `false`" guidance + "Propose this" + "narrower globs" touches_paths instruction + Parallelism-by-default subsection with dry-run command + path_overlap_with cross-link.

### PHASE_011 at a glance
| Unit | Done | Evidence |
|------|------|----------|
| unit_bugfix_001 | ISSUE_001 Windows Python-detection | 5 tests pinning doc-shape contract |
| unit_bugfix_002 | ISSUE_002 Claude Code Stop-hook retired | 12 new + 9 rewritten hook tests |
| unit_045 | Parallel Execution Model in architecture.md | 10 tests pin structure + position order |
| unit_046 | phase-contract parallelism fields + decomposition section | 11 tests pin table + 5-step recipe |
| unit_047 | new parallel-execution.md deep-dive + overlap-reason fix | 10 tests + negative assertion guard |
| unit_048 | create.md Phase 2 + Phase 4 bootstrap flow | 11 tests pin verbatim questions + new fields |

Suite: 228 → 286 across the phase (with 1 Windows skip).

### PR review checklist (pr-review-checklist.md)
- [x] All 6 units have `validation_evidence` in phase-graph.json
- [x] No linter/type errors (stdlib-only Python; docs-only changes)
- [x] Codebase patterns matched
- [x] Unit tests pass 285/286 + 1 OS-specific skip
- [x] Not deploy-affecting (skill distribution repo)
- [x] Phase doc + checkpoint + state current
- [x] Both tracked issues (ISSUE_001, ISSUE_002) resolved

## What Failed (if anything)
None.

## What Is Next
**Open PHASE_011 PR** (`feat/phase-011-documentation` → `main`), run the `code-review` skill, squash-merge per [harness-git.md](.claude/rules/harness-git.md) autonomous-merge authorization.

**Then PHASE_012 `unit_051`:** add parallelism readiness checklist to [references/parallel-execution.md](skills/development-harness/references/parallel-execution.md) covering `touches_paths` on every parallelism-eligible unit, no shared-aggregator units, CI handles multi-commit pushes. Note: unit_047 already landed a "Readiness checklist" section in parallel-execution.md with 8 checkboxes — unit_051 will likely be an extension/refinement of that existing list rather than a fresh section. Read the existing list first before drafting edits.

## Blocked By
None.

## Evidence
- [skills/development-harness/commands/create.md](skills/development-harness/commands/create.md): Phase 2 Execution Mode category + Phase 4 Step 2 additions.
- [skills/development-harness/scripts/tests/test_create_bootstrap_parallelism_questions.py](skills/development-harness/scripts/tests/test_create_bootstrap_parallelism_questions.py): new 190-line test module, 11 cases.
- `python -m py_compile` → 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.test_create_bootstrap_parallelism_questions -v` → **11/11** (0.004s).
- `python -m unittest discover skills/development-harness/scripts/tests` → **285/286** + 1 OS skip in 41.6s (up from 275).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, **resolved 2026-04-20**): Windows Python-detection. Fixed in unit_bugfix_001.
- **ISSUE_002** (high, **resolved 2026-04-20**): Claude Code Stop-hook one-shot continuation. Fixed in unit_bugfix_002.

All tracked issues resolved.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_011 PR opens now.
- **Branch:** `feat/phase-011-documentation` → squash-merge to `main`.
- **Next branch:** `feat/phase-012-release-readiness` (after PHASE_011 squashes in).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 48 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_011 progress: **6/6 units done** — phase CLOSED.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → 206 → 210 → 215 → 222 → 223 → 228 → 244 → 254 → 265 → 275 → **286** across phases so far.

## Batch (current or last)

Reflects `state.execution.fleet`.

- **Batch ID:** none
- **Mode:** idle

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|

### Conflicts
No conflicts.

---
*Updated: 2026-04-20T12:00:00Z*
