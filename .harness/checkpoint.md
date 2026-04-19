# Harness Checkpoint

## Last Completed
**unit_008 (PHASE_002):** Locked in the frontier-resolution contract with exhaustive topology coverage in [test_select_next_unit.py](skills/development-harness/scripts/tests/test_select_next_unit.py).

Coverage added:

- **Linear** (`A -> B -> C`): head is the only ready unit at start; middle becomes ready only after head is marked `completed`.
- **Diamond** (`A -> B`, `A -> C`, `B + C -> D`): both siblings surface after the root is done; the bottom unit requires both siblings completed; the bottom stays blocked while one sibling is still `in_progress`.
- **Disconnected**: two independent phase subgraphs both surface their current heads (phase-list, then unit-list ordering); independent progress on each subgraph is respected.
- **Partially completed**: middle-gap chains resolve to the earliest unblocked unit; parallel-sibling subsets with one completed sibling still surface the rest.
- **Phase-complete-pending signalling**: when an earlier phase has all units done but is not yet marked `completed`, the no-flag selector returns `found=False, phase_complete=True, all_complete=False` so the invoke flow runs the review; once the phase is marked completed, the later phase's unit becomes the found head and `phase_complete` drops back to False.
- **Malformed-unit error coverage** (extends unit_007's two cases): non-dict unit (exit 2, "must be an object"), missing `id` (exit 2, "missing"). All error paths point to `validate_harness.py`.

## What Failed (if anything)
None. One test initially had the wrong assertion on `phase_complete_pending`-blocks-later-phase; the assertion was fixed to match the intended semantics (later phase blocks when its dep is not yet marked completed even if that dep's units are all done).

## What Is Next
**Complete unit_009 (PHASE_002):** New [skills/development-harness/scripts/compute_parallel_batch.py](skills/development-harness/scripts/compute_parallel_batch.py): stdlib `fnmatch` glob-overlap matrix + literal-prefix match; greedy-pack under `parallelism.max_concurrent_units`; emit `{batch, excluded, batch_id}` where every excluded entry carries a machine-readable reason.

## Blocked By
None.

## Evidence
- [test_select_next_unit.py](skills/development-harness/scripts/tests/test_select_next_unit.py): `TestFrontierTopologies` (10 cases) and `TestNoLegacyFallback` (4 cases total after unit_008's additions).
- `python -m unittest discover skills/development-harness/scripts/tests` -> 83/83 pass (up from 71 at end of unit_007).
- No production code changes this unit -- the v2 selector from unit_007 already implements the right semantics; this unit is pure coverage.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Stop-hook portability when only `python` is on PATH. Workspace-level fix active. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **Hook continuation regression (unscheduled):** After unit_007 the stop hook decided to stop and deleted `.harness/.invoke-active`; manual `/invoke-development-harness` was required to pick up unit_008. Root cause not yet pinpointed (could be Claude Code's `stop_hook_active` guard tripping on a deep continuation, could be a transient selector/subprocess error). Flag-re-creation at invoke-start (step 1) handles the symptom; if this recurs, investigate by adding per-fire telemetry to continue-loop.py.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_002 PR opens after unit_010.
- **Branch:** `feat/phase-002-frontier-selector`.
- **Merge:** squash; autonomous per the updated harness-git rule.

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- loop_budget bumped from 10 to 12 to accommodate longer phases; revisit this as a proper config knob in PHASE_011 doc pass.

---
*Updated: 2026-04-19T20:30:00Z*
