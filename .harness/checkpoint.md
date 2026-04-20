# Harness Checkpoint

## Last Completed
**unit_056 (PHASE_013):** Programmatic self-test run against the Tasklet fixture — **all 3 seeded conditions fired exactly as designed**.

### What landed

[test_self_test_run.py](skills/development-harness/scripts/tests/integration/test_self_test_run.py) spawns a temp git repo, reads `fixtures/self-test/phase-graph.json` + `config.json`, and drives the full `compute_parallel_batch → dispatch_batch → fake-sub-agent-commits → merge_batch` pipeline for multiple turns until the fixture reaches a stable terminal state.

### Trace excerpt ([fixtures/self-test/trace.log](skills/development-harness/scripts/tests/fixtures/self-test/trace.log))

```
--- Turn 1 ---
  Frontier: ['unit_a1', 'unit_a2', 'unit_a3', 'unit_b1', 'unit_b2', 'unit_b3']
  Batch:    ['unit_a1', 'unit_a2']
  Excluded: unit_a3 (reason: path_overlap_with:unit_a2)
  Merge outcome: ok | merged=['unit_a1', 'unit_a2'] conflicted=[]

--- Turn 2 ---
  Batch:    ['unit_a3']
  Merge outcome: ok | merged=['unit_a3'] conflicted=[]

--- Turn 3 ---
  Batch:    ['unit_b1', 'unit_b2', 'unit_b3']
  Merge outcome: partial | merged=['unit_b1', 'unit_b3'] conflicted=['unit_b2']
    failed:  unit_b2 (category: scope_violation)

Batch sizes observed: [2, 1, 3]
Final status counts: {'completed': 5, 'pending': 1}
```

### Seeded-condition verification
| Condition | Expected | Observed | Pass? |
|-----------|----------|----------|-------|
| Batch ≥ 2 | ≥ 1 turn with batch size ≥ 2 | Turn 1 size 2, Turn 3 size 3 | ✓ |
| Overlap-matrix rejection | `unit_a3` excluded with `path_overlap_with:unit_a2` | Exact match on Turn 1 | ✓ |
| Scope violation | `unit_b2` rejected with `src/seeds/users.json` in `conflict.paths` | Match on Turn 3 | ✓ |

### Final state
- **5 units completed** (all of PHASE_A + unit_b1 + unit_b3).
- **1 unit pending** (`unit_b2` — scope violation). The phase-graph leaves b2 pending because the fleet's `failed` status doesn't auto-flip the phase-graph entry; a human must fix the description/touches_paths discrepancy + retry.
- **Only `unit_b2`'s worktree survives** (scope-violation path preserves it by design in `merge_batch.py`). All other worktrees torn down; no `harness/batch_*/*` branches remain.

### Implementation notes
Caught two bugs during development:
1. `FIXTURE_DIR` path from `__file__` had a double `scripts/` component. Fixed by using `parents[1]` which already lands on `tests/`.
2. Orphan check via `rglob` saw the batch-parent dir in addition to leaf unit dirs, producing false positives. Fixed by iterating only two levels deep (`batch_dir.iterdir()`) and comparing the leaf-name set directly.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_057 (PHASE_013):** produce a wall-clock data table comparing parallelism-enabled vs sequential-baseline runs.

- The **parallel** timing is captured in `trace.log` from unit_056 (3 turns, ~2s).
- The **sequential baseline** needs a second run with `config.execution_mode.parallelism.enabled: false` — forces batch-of-1 in-tree fast path throughout, 6 turns one unit at a time.
- Compare wall-clock between the two; commit the comparison data as a short markdown snippet that will be embedded in POST-MORTEM.md (unit_058).
- Verify no orphaned worktrees/branches remain (already done in unit_056's test; this just re-confirms in the commit evidence).

Validation: comparison data committed under the fixture dir; grep verifies the table includes both parallel + sequential rows + a wall-clock ratio.

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/tests/integration/test_self_test_run.py](skills/development-harness/scripts/tests/integration/test_self_test_run.py): new 300-line integration module, 1 case.
- [skills/development-harness/scripts/tests/fixtures/self-test/trace.log](skills/development-harness/scripts/tests/fixtures/self-test/trace.log): captured trace.
- `python -m py_compile` → 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.integration.test_self_test_run -v` → **1/1** in 2.1s.
- `python -m unittest discover skills/development-harness/scripts/tests` → **345/346** + 1 OS skip in 40.6s (up from 345 — 1 new case + trace.log artifact).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, **resolved 2026-04-20**): Windows Python-detection. Fixed in unit_bugfix_001.
- **ISSUE_002** (high, **resolved 2026-04-20**): Claude Code Stop-hook one-shot continuation. Fixed in unit_bugfix_002.

All tracked issues resolved.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_013 PR opens after unit_058 (last unit).
- **Branch:** `feat/phase-013-harness-self-test`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 54 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_013 progress: **3/5 units done** (054 fixture scaffold, 055 /create artifacts, 056 end-to-end self-test + trace.log). Remaining: 057 timing table, 058 POST-MORTEM.md + link from parallel-execution.md.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → 206 → 210 → 215 → 222 → 223 → 228 → 244 → 254 → 265 → 275 → 286 → 291 → 304 → 312 → 321 → 332 → 345 → **346** across phases so far.

## Batch (current or last)

Reflects `state.execution.fleet`.

- **Batch ID:** none
- **Mode:** idle

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|

### Conflicts
No conflicts.

---
*Updated: 2026-04-20T14:35:00Z*
