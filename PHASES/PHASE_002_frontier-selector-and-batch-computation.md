# PHASE_002: Frontier Selector and Batch Computation

## Objective
Replace the "pick one next unit" selector with a frontier model and add a deterministic parallel-batch computer. Both scripts are consumed by PHASE_005 and PHASE_007; this phase introduces no runtime behavior change on its own.

## Why This Phase Exists
Parallel execution needs two pieces the current harness lacks: (1) an answer to "which units are ready right now" (the frontier), and (2) a greedy packer that picks the largest safe batch given overlap rules and capacity. Splitting these from the invoke rewrite lets us land and test them in isolation before the live execution flow depends on them.

## Scope
- Rewrite `skills/development-harness/scripts/select_next_unit.py` around frontier computation. Add `--frontier` and `--max N` flags. Without flags, return the head of the frontier so the stop hook's JSON contract is preserved. No legacy list-order fallback — malformed units produced by an invalid harness (which the validator should have caught) cause the selector to error, not paper over.
- New `skills/development-harness/scripts/compute_parallel_batch.py`:
  - Inputs: frontier JSON, `parallelism` config, phase-graph (for `touches_paths` lookup).
  - Filter: drop units where `parallel_safe == false`; if `require_touches_paths == true`, drop units with empty `touches_paths`.
  - Glob-overlap matrix using stdlib `fnmatch` + literal-prefix match. Any pair whose declared globs overlap is mutually exclusive.
  - Greedy pack under `max_concurrent_units`.
  - Output: `{batch, excluded, batch_id}` where `excluded` entries carry a machine-readable reason.
- Exclusion reason strings (exact values): `"not_parallel_safe"`, `"path_overlap_with:<unit_id>"`, `"capacity_cap"`.

> ⚠️ **Edit target:** `skills/development-harness/**` only.

## Non-goals
- Wiring the selector or batcher into the invoke flow — that is PHASE_007.
- Dispatching or merging — PHASE_005.
- Overriding PHASE_001's required-field rules. This phase assumes a valid v2 harness.

## Dependencies
- PHASE_001 (new fields, updated validator).

## User-visible Outcomes
- `python .harness/scripts/select_next_unit.py --frontier --max 3` prints a JSON list of up to 3 ready units.
- `python .harness/scripts/compute_parallel_batch.py --input <frontier.json> --config <config.json>` prints the batch decision with explicit exclusion reasons.
- The stop hook continues to work unchanged against the no-flag selector call.

## Units of Work

| ID | Description | Acceptance Criteria | Validation Method | Status |
|----|-------------|--------------------|--------------------|--------|
| unit_007 | Rewrite `select_next_unit.py` around frontier computation; add `--frontier` and `--max N` flags; preserve stop-hook JSON contract on no-flag call | No-flag output shape identical to v1 (found/phase_id/unit_id/…); `--frontier` returns a JSON array of ready units; no legacy fallback | `python -m unittest skills.development-harness.scripts.tests.test_select_next_unit` | pending |
| unit_008 | Frontier resolution strictly from `depends_on`; error loudly on malformed units | Linear, diamond, disconnected, partially-completed graphs all resolved correctly; malformed unit raises a clear error | `test_select_next_unit` — fixture graphs for each topology | pending |
| unit_009 | New `compute_parallel_batch.py` with stdlib `fnmatch` overlap matrix; greedy-pack under `max_concurrent_units` | Non-overlapping paths cap out at `max_concurrent_units`; overlapping pairs never co-exist in batch; `batch_id` is UTC timestamp or UUID | `python -m unittest skills.development-harness.scripts.tests.test_compute_parallel_batch` | pending |
| unit_010 | Machine-readable exclusion reasons with matching unit tests | Each reason (`not_parallel_safe`, `path_overlap_with:<id>`, `capacity_cap`) fires on a crafted input and is asserted by a dedicated test | `test_compute_parallel_batch` — one test per reason | pending |

## Validation Gates
- **Layer 1:** Python syntax valid on both scripts.
- **Layer 2:** `test_select_next_unit.py` (expanded) and `test_compute_parallel_batch.py` (new) pass. Existing stop-hook test cases (via the no-flag call) continue to pass.

## Deployment Implications
Not deploy-affecting.

## Completion Evidence Required
- `python -m unittest skills.development-harness.scripts.tests.test_select_next_unit` exits 0 with new topology cases.
- `python -m unittest skills.development-harness.scripts.tests.test_compute_parallel_batch` exits 0 with all exclusion-reason cases.
- Manual spot-check: `python skills/development-harness/scripts/compute_parallel_batch.py --help` runs.

## Rollback / Failure Considerations
The live harness still uses the frozen v1 `.harness/scripts/select_next_unit.py`. If the rewrite breaks tests, the invoke loop is unaffected. Revert the phase commits on failure.

## Status
pending
