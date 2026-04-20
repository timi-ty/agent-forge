# Harness Checkpoint

## Last Completed
**unit_047 (PHASE_011):** New [references/parallel-execution.md](skills/development-harness/references/parallel-execution.md) — the operator-facing deep-dive that [architecture.md](skills/development-harness/references/architecture.md) (unit_045) and [phase-contract.md](skills/development-harness/references/phase-contract.md) (unit_046) point forward to.

### Seven numbered sections
1. **Dispatch lifecycle** — ASCII flow diagram walking `idle → dispatched → merging → idle` with the exact invariant that the stop hook never sees a non-idle fleet at turn-end during normal operation; crash recovery is `/sync-development-harness`, not another invoke turn.
2. **Overlap-matrix algorithm** — greedy-packer pseudocode + four gates (parallel_safe+touches_paths, cross-phase silent-defer, capacity_cap, pairwise overlap via fnmatch) + verbatim exclusion-reason table matching the actual code output.
3. **Merge-order rationale** — why the order is stable by design: determinism beats throughput, per-unit scope checks make "safer orders" moot, real conflicts are rare when `touches_paths` is right. Pins `--no-ff` mode and `git log --first-parent` attribution readability.
4. **Failure-mode catalog** — 5-row table covering `scope_violation`, `merge_conflict`, `post_merge_validation_failed`, `infrastructure`, `ambiguity`. Each row names source, `conflict_strategy` effect, and whether it counts toward the session kill switch.
5. **Recovery procedures** — four scenarios with numbered instructions: mid-dispatch crash, mid-merge crash, kill-switch tripped, scope-violation dispute. Includes the explicit "never force-delete the lock" warning.
6. **Readiness checklist** — 8 markdown checkboxes gating "should you enable parallelism".
7. **Observability quick reference** — all four `.harness/logs/<batch_id>/` artifacts + the exact Batch Timings format string.

### Bundled doc/code consistency fix
While grep-ing the code to write parallel-execution.md, I discovered that unit_045 and unit_046 had introduced a doc/code drift: both mine new docs used `touches_overlap` as the overlap exclusion reason, but `compute_parallel_batch.py` line 170 actually emits `path_overlap_with:<id>`. Fixed in this commit:

- `architecture.md` line 133 → `path_overlap_with`.
- `phase-contract.md` lines 138 + 161 → `path_overlap_with`.
- `test_architecture_parallel_section.py` + `test_phase_contract_parallelism_fields.py` — assertions updated.
- `parallel-execution.md` uses `path_overlap_with` from the start AND carries an explicit negative assertion `assertNotIn("touches_overlap", body)` so a future edit can't silently reintroduce the typo.

### New regression test
[test_parallel_execution_reference.py](skills/development-harness/scripts/tests/test_parallel_execution_reference.py) — 10 cases across 3 classes:

- **TestParallelExecutionDocStructure (7)** — each numbered section exists and carries its substantive anchors (all three fleet.mode states, all three exclusion-reason strings, all five conflict categories, the Batch Timings format string exactly, markdown-checkbox syntax in the readiness checklist, `--no-ff`, first-parent log attribution).
- **TestParallelExecutionDocCrossLinks (2)** — new doc links both architecture.md and phase-contract.md; architecture.md's forward-link survives.
- **TestExclusionReasonConsistencyWithCode (1)** — negative assertion against `touches_overlap`; guards against the regression caught in this unit.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_048 (PHASE_011):** update [commands/create.md](skills/development-harness/commands/create.md) bootstrap flow:

**Phase 2 (structured questions)** — add two new questions:
1. `Enable parallel unit execution? (y/n, default n)` → writes `config.execution_mode.parallelism.enabled`.
2. `Break-on-schema-bump vs migrate? (break/migrate, default break)` → writes `config.execution_mode.versioning.break_on_schema_bump`.

**Phase 4 (phase-graph compilation)** — instruct the agent to:
- Propose `touches_paths` per unit by reading the unit's description + acceptance criteria.
- Default `parallel_safe: false` when the unit's blast radius is unknown.

This is the last documentation unit before PHASE_011 closes. Validation: grep Phase 2 + Phase 4 sections for the new question/instruction text + structural presence test.

## Blocked By
None.

## Evidence
- [skills/development-harness/references/parallel-execution.md](skills/development-harness/references/parallel-execution.md): new ~240-line deep-dive.
- [skills/development-harness/references/architecture.md](skills/development-harness/references/architecture.md): `touches_overlap` → `path_overlap_with` fix (line 133).
- [skills/development-harness/references/phase-contract.md](skills/development-harness/references/phase-contract.md): same fix (lines 138, 161).
- [skills/development-harness/scripts/tests/test_parallel_execution_reference.py](skills/development-harness/scripts/tests/test_parallel_execution_reference.py): new 180-line module, 10 cases.
- [skills/development-harness/scripts/tests/test_architecture_parallel_section.py](skills/development-harness/scripts/tests/test_architecture_parallel_section.py) + [test_phase_contract_parallelism_fields.py](skills/development-harness/scripts/tests/test_phase_contract_parallelism_fields.py): assertions updated for the corrected reason string.
- `python -m py_compile` → 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.test_parallel_execution_reference -v` → **10/10** (0.003s).
- `python -m unittest discover skills/development-harness/scripts/tests` → **274/275** + 1 OS skip in 37.6s (up from 265).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, **resolved 2026-04-20**): Windows Python-detection. Fixed in unit_bugfix_001.
- **ISSUE_002** (high, **resolved 2026-04-20**): Claude Code Stop-hook one-shot continuation. Fixed in unit_bugfix_002.

All tracked issues resolved.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_011 PR opens after unit_048 closes.
- **Branch:** `feat/phase-011-documentation`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 47 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_011 progress: **5/? units done** (bugfix_001 + bugfix_002 + 045 + 046 + 047). Remaining: 048 (create.md Phase 2 + Phase 4 updates).
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → 206 → 210 → 215 → 222 → 223 → 228 → 244 → 254 → 265 → **275** across phases so far.

## Batch (current or last)

Reflects `state.execution.fleet`.

- **Batch ID:** none
- **Mode:** idle

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|

### Conflicts
No conflicts.

---
*Updated: 2026-04-20T11:35:00Z*
