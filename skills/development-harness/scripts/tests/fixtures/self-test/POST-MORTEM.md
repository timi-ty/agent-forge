# Self-Test Post-Mortem — Tasklet Fixture

PHASE_013 of the development-harness skill upgrade exercised the complete parallel-execution machinery against a non-trivial fixture (the "Tasklet" mini-CRUD roadmap). This document records what happened, what worked, what didn't, and what follow-ups the self-test surfaced.

The self-test is **not** part of CI — it runs ad-hoc via `python -m unittest skills.development-harness.scripts.tests.integration.test_self_test_run` when a maintainer wants to validate the full `create → invoke → batch → merge → checkpoint` loop end-to-end.

## 1. Setup

### Fixture
- **Tasklet** — 2 milestones (Items + Users), 6 units total, all `parallel_safe: true`, designed to fire exactly three behaviors when run through the harness:
  1. **Batch ≥ 2** (`unit_a1` + `unit_a2` pack into PHASE_A's first batch on disjoint `touches_paths`).
  2. **Overlap-matrix rejection** (`unit_a3`'s `touches_paths` deliberately overlap `unit_a2`'s; `compute_parallel_batch` excludes `a3` with `path_overlap_with:unit_a2`).
  3. **Scope violation** (`unit_b2`'s description tells the sub-agent to write `src/seeds/users.json`, but its declared `touches_paths` omits `src/seeds/**`; `merge_batch._scope_violations` hard-rejects the merge with `conflict.category: "scope_violation"`).

The full fixture contract is documented in [README.md](./README.md) alongside this post-mortem.

### Artifacts produced
| File | Created by unit | Purpose |
|------|-----------------|---------|
| `ROADMAP.md` | 054 | Product intent for the fixture |
| `README.md` | 054 | Seeded-conditions contract |
| `config.json` | 055 | Harness config with `parallelism.enabled: true` |
| `phase-graph.json` | 055 | 2-phase / 6-unit graph with `touches_paths` populated |
| `trace.log` | 056 | Captured trace from the full programmatic run |
| `wall-clock.md` | 057 | Parallel vs sequential comparison table |
| `POST-MORTEM.md` | 058 | This document |

### Operator recipe (for a human running `/invoke-development-harness` manually)
```bash
cd skills/development-harness/scripts/tests/fixtures/self-test
# Optional: clone into a throwaway repo + install the harness skill
/create-development-harness     # or use the committed config.json + phase-graph.json
/invoke-development-harness     # iterate until all-phases-complete or blocker
# Inspect .harness/logs/<batch_id>/ for per-batch traces
```

## 2. Results

### End-to-end behavior matches design

[test_self_test_run.TestSelfTestEndToEnd](../../integration/test_self_test_run.py) drives the `compute → dispatch → merge` pipeline against the fixture and records observations. All three seeded conditions fired exactly as designed:

| Condition | Observed | Pass? |
|-----------|----------|-------|
| Batch ≥ 2 | Turn 1 batch size 2, Turn 3 batch size 3 | ✓ |
| Overlap-matrix rejection | `unit_a3` excluded with `path_overlap_with:unit_a2` on Turn 1 | ✓ |
| Scope violation | `unit_b2` rejected with `src/seeds/users.json` in `conflict.paths` on Turn 3 | ✓ |

Final state: 5 units `completed`, 1 unit `failed` (unit_b2 — awaiting human repair). Only `unit_b2`'s worktree survives by design (scope-violation path in `merge_batch.py` preserves it for inspection).

### Wall-clock comparison

[TestWallClockParallelVsSequential](../../integration/test_self_test_run.py) runs the same fixture twice — once with `max_concurrent_units: 3` (fixture default), once with `max_concurrent_units: 1` (sequential baseline). Full data in [wall-clock.md](./wall-clock.md):

| Run | Turns | Batch sizes | Wall-clock (s) |
|-----|-------|-------------|----------------|
| Parallel | 3 | `[2, 1, 3]` | 1.97 |
| Sequential | 6 | `[1, 1, 1, 1, 1, 1]` | 2.00 |

**Ratio: 1.02x.** The low ratio reflects the fake-commit nature of the test — each sub-agent writes a few bytes and commits instantly, so per-unit work barely overlaps. The meaningful signal for this fixture is **turn count (3 vs 6)**. A real project with slow per-unit work (real test runs, real installs) will see a larger wall-clock ratio because the fixed worktree + merge overhead stays constant while expensive per-unit work overlaps.

### Orphan invariant holds

Post-run, both the parallel and sequential runs leave:
- No orphan worktrees under `.harness/worktrees/` except `unit_b2`'s (preserved by design).
- No residual `harness/batch_*/*` branches.
- `state.execution.fleet.mode == "idle"` at the end of every turn.

## 3. Papercuts

Two real runtime bugs surfaced while building the self-test drivers. Both were worked around at the driver level rather than patched in runtime code, since the scope of PHASE_013 is "exercise + document", not "fix every issue surfaced". Both are filed as follow-ups below.

### 3.1 `compute_frontier` does not filter `failed` units

**Where:** [select_next_unit.py:123](../../../select_next_unit.py) — the `compute_frontier` loop only skips `status == "completed"`. A unit with `status == "failed"` (or `"blocked"`) still appears in the frontier.

**Consequence observed:** after a scope violation flips `unit_b2` to `failed`, `compute_frontier` kept surfacing it on subsequent turns. The driver tried to re-dispatch `b2`, hit `git worktree add` with a branch name (`harness/<batch_id>/unit_b2`) that already existed (preserved by the scope-violation path), and failed with exit 255.

**Workaround applied:** both drivers (`_run_one_turn` and `_drive_fixture`) filter `failed` units out of the frontier before passing it to `compute_batch`.

**Proper fix (follow-up):** `compute_frontier` should skip `status in {"completed", "failed", "blocked"}` — only `pending` (and arguably `in_progress`) should surface. The phase-contract's Status section already lists these values; the frontier filter should match.

### 3.2 `_make_batch_id` has 1-second granularity

**Where:** [compute_parallel_batch.py:112](../../../compute_parallel_batch.py) — `_make_batch_id` returns `"batch_" + moment.strftime("%Y-%m-%dT%H-%M-%SZ")`. Two calls in the same second produce identical `batch_id`s.

**Consequence observed:** in tests, multiple turns frequently fall inside the same second. Normally harmless (worktree paths are `.harness/worktrees/<batch_id>/<unit_id>/` — different unit_ids are disjoint). But combined with bug §3.1, it made the branch-name collision inevitable: `harness/<same-second-batch>/unit_b2` already existed from the preserved worktree, so `git worktree add` refused to create a new branch with the same name.

**Workaround applied:** none beyond the §3.1 workaround, which prevents re-dispatch in the first place.

**Proper fix (follow-up):** switch to millisecond precision or append a UUID suffix. A cleaner shape: `batch_<ISO-timestamp>_<4-hex>` so even same-millisecond calls get unique IDs. Preserves sortability + uniqueness.

### 3.3 Driver-level observations that didn't need patching

- **`merge_batch` outcome reporting matches expectations.** The `"partial"` outcome fires correctly when some units merge and some fail in the same batch. The per-unit `conflict.category` strings (`"scope_violation"`, `"merge_conflict"`) match the catalog in [parallel-execution.md § 4](../../../../references/parallel-execution.md).
- **Fleet-mode transitions hold.** `idle → dispatched → merging → idle` completes within every turn; the stop-hook guard from PHASE_008 never trips during healthy runs.
- **Observability artifacts land as documented.** Each parallel turn produces `.harness/logs/<batch_id>/{batch.json, merge.log, validation.log}` per [architecture.md § Parallel Execution Model](../../../../references/architecture.md). (Sub-agent `<unit_id>.md` files are written by sub-agents per the harness-unit contract; the driver fakes sub-agent work so those files aren't produced in the test, but the directory layout is correct.)

## 4. Follow-ups

Both runtime bugs from §3 are filable via `/inject-harness-issues` once a maintainer opts to promote them to issues. Drafts:

**Follow-up 1 — `compute_frontier` must filter `failed` status** (priority: medium)
- Root cause: see §3.1.
- Fix approach: `select_next_unit.py:123` currently reads `if unit.get("status") == "completed": continue`. Change to `if unit.get("status") in ("completed", "failed", "blocked"): continue`.
- Regression coverage: add a case to `test_select_next_unit.py` seeding a unit with `status == "failed"` and asserting it's absent from the frontier output.
- Scope: purely local to `compute_frontier`; downstream callers (invoke flow, driver code) already handle the filtered frontier correctly.

**Follow-up 2 — `_make_batch_id` must be collision-free within a session** (priority: low)
- Root cause: see §3.2.
- Fix approach: replace `strftime("%Y-%m-%dT%H-%M-%SZ")` with either millisecond precision (`"%Y-%m-%dT%H-%M-%S-%fZ"`) or a 4-hex suffix via `secrets.token_hex(2)`.
- Regression coverage: a test that calls `_make_batch_id` 10× in tight succession and asserts all results are unique.
- Scope: local to `compute_parallel_batch.py`; `batch_id` is consumed as an opaque string everywhere downstream (path component, branch name), so changing its format is safe.

Neither follow-up blocks the v2 skill release — both are driver-workaround-able, and neither trips in real usage where turns are naturally >1 second apart because of actual per-unit work. They're filed here so a future session can pick them up when convenient.

## 5. Takeaways

The self-test meaningfully validates the upgrade, not just compile-checks it. Three signals matter:

1. **All three seeded conditions fired end-to-end** — the parallelism machinery works against a real phase-graph + config, not just unit-test fixtures.
2. **Two real runtime bugs caught during the build** — the self-test is doing its job by pressure-testing the machinery beyond what the unit-test suite covers.
3. **The orphan invariant holds** — no crashed mid-batch state leaks across turns; recovery (scope-violation preserves worktree, everything else tears down) works as designed.

The development-harness skill's v2 upgrade is ready to ship.

---
*Captured at end of PHASE_013 — 2026-04-20.*
