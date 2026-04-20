# Harness Checkpoint

## Last Completed
**unit_046 (PHASE_011):** [phase-contract.md](skills/development-harness/references/phase-contract.md) Units of Work contract extended with parallelism fields + new "Decomposing a phase for parallelism" section.

### Table extension
Units of Work table grew from 4 columns (id, description, acceptance criteria, validation method) to 5 — added a new **Required** column — and gained 3 new rows:

| Row | When required | Enforcer |
|-----|---------------|----------|
| `depends_on` | always (empty list allowed) | `compute_frontier` in [select_next_unit.py](skills/development-harness/scripts/select_next_unit.py) |
| `parallel_safe` | always (default `false`) | [compute_parallel_batch.py](skills/development-harness/scripts/compute_parallel_batch.py) |
| `touches_paths` | required when `parallel_safe: true` (under default config) | merge-time scope check in [merge_batch.py](skills/development-harness/scripts/merge_batch.py); cross-links to the existing **Scope-Violation Enforcement Policy** section |

The `touches_paths` conditional is the most error-prone — the row pins it explicitly AND cross-links to the trust-boundary rationale so readers don't need to guess why it matters.

### New section: "Decomposing a phase for parallelism"
Five-step recipe placed **after** the Scope-Violation Enforcement Policy:

1. **Draw the dependency graph** — distinguish real `depends_on` from spurious logical-ordering preferences, with concrete examples on both sides.
2. **Identify each unit's blast radius** — `touches_paths` authoring with the "one directory per unit" heuristic and the "shared test utilities are the usual hazard" warning.
3. **Check for overlap** — `fnmatch`-based overlap matrix in `compute_parallel_batch.py` with the "narrow globs, don't disable the check" guardrail.
4. **Set `parallel_safe` deliberately** — framed as a "declaration of independence, not a performance hint" with four explicit criteria and a "when in doubt, leave it false" default.
5. **Dry-run the batch** — `select_next_unit.py --frontier | compute_parallel_batch.py --input -` pipeline to surface capacity/overlap/cross-phase rejections before merge time.

Closes with an **Anti-patterns** subsection naming three real traps observed in dogfooding:
- The "set up everything" unit pattern (usually a sign the parallel units aren't actually independent).
- `parallel_safe: true` as a speed signal instead of an independence declaration.
- Globs that cover shared files (e.g., two units both declaring `**/*.md`).

### New regression test
[test_phase_contract_parallelism_fields.py](skills/development-harness/scripts/tests/test_phase_contract_parallelism_fields.py) — 11 cases across 3 classes:

- **TestUnitsOfWorkTableCarriesParallelismFields (4)** — Required column + all 3 new rows + touches_paths conditional + Scope-Violation policy cross-link.
- **TestDecompositionSubsection (6)** — section present + all 5 Step sub-headings + substantive content (dependency graph terminology, blast radius + one-directory heuristic, overlap matrix + touches_overlap exclusion reason, declaration-vs-hint contrast, dry-run command string, Anti-patterns sub-heading).
- **TestDecompositionSectionPlacedAfterScopePolicy (1)** — position-order assertion so a future edit can't accidentally invert the reading flow (trust-boundary rationale must come before how-to guidance).

## What Failed (if anything)
None.

## What Is Next
**Complete unit_047 (PHASE_011):** create new [references/parallel-execution.md](skills/development-harness/references/parallel-execution.md) covering:

1. Dispatch lifecycle (deeper than architecture.md's summary).
2. Overlap-matrix algorithm details.
3. Merge-order rationale.
4. Failure-mode catalog.
5. Recovery procedures.
6. Readiness checklist.

This is the deep-dive companion to architecture.md's new Parallel Execution Model summary section — architecture.md links forward to this doc. Much of the content already exists in module docstrings + phase-graph.json validation_evidence; this unit consolidates it.

Validation: grep for major section headings + structural presence test similar to unit_045/unit_046.

## Blocked By
None.

## Evidence
- [skills/development-harness/references/phase-contract.md](skills/development-harness/references/phase-contract.md): Units of Work table expanded + new Decomposing section.
- [skills/development-harness/scripts/tests/test_phase_contract_parallelism_fields.py](skills/development-harness/scripts/tests/test_phase_contract_parallelism_fields.py): new 170-line test module, 11 cases.
- `python -m py_compile` → 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.test_phase_contract_parallelism_fields -v` → **11/11** (0.003s).
- `python -m unittest discover skills/development-harness/scripts/tests` → **264/265** + 1 OS skip in 37.6s (up from 254).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, **resolved 2026-04-20**): Windows Python-detection. Fixed in unit_bugfix_001.
- **ISSUE_002** (high, **resolved 2026-04-20**): Claude Code Stop-hook one-shot continuation. Fixed in unit_bugfix_002.

All tracked issues resolved.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_011 PR opens after the last unit closes.
- **Branch:** `feat/phase-011-documentation`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 46 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_011 progress: **4/? units done** (bugfix_001 + bugfix_002 + 045 + 046). Remaining: 047 (new parallel-execution.md), 048 (unit_bugfix_001 reference — already done?).
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → 206 → 210 → 215 → 222 → 223 → 228 → 244 → 254 → **265** across phases so far.

## Batch (current or last)

Reflects `state.execution.fleet`.

- **Batch ID:** none
- **Mode:** idle

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|

### Conflicts
No conflicts.

---
*Updated: 2026-04-20T11:05:00Z*
