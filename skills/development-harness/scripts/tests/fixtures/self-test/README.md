# Self-Test Fixture — Tasklet

This directory holds a throwaway workspace used by PHASE_013 (harness-self-test) to exercise the completed parallel-execution upgrade against a non-trivial but bounded roadmap. It is **not** part of CI — the fixture runs ad-hoc when a maintainer wants to validate the full `create → invoke → batch → merge → checkpoint → stop-hook continuation → next batch` loop end-to-end.

## Directory contents

| File | Created by | Purpose |
|------|------------|---------|
| `ROADMAP.md` | unit_054 | Product intent for Tasklet (mini CRUD tracker). Read by `/create-development-harness`. |
| `README.md` | unit_054 | This file — documents the seeded conditions. |
| `phase-graph.json` (planned) | unit_055 | The compiled phase graph + `touches_paths` per unit, captured after running `/create-development-harness` on this fixture. |
| `config.json` (planned) | unit_055 | Generated harness config; `parallelism.enabled = true`. |
| `trace.log` (planned) | unit_056 | Captured invoke traces showing each batch composition + merge outcome. |
| `POST-MORTEM.md` (planned) | unit_058 | Wall-clock data table + papercut list. Linked from `../../../references/parallel-execution.md`. |

## Roadmap shape

Two phases, six units total. Phase A = Items, Phase B = Users. No phase-level dependency between A and B (they can be worked on in either order; the harness's `allow_cross_phase: false` default keeps batches phase-scoped).

```
PHASE_A (Items)
├── unit_a1  "Item model"      parallel_safe=true
│   touches_paths: ["src/items/model.py"]
├── unit_a2  "Item routes"     parallel_safe=true
│   touches_paths: ["src/items/routes.py", "src/router.py"]
└── unit_a3  "Item bulk-action" parallel_safe=true, depends_on: []
    touches_paths: ["src/items/routes.py"]

PHASE_B (Users)
├── unit_b1  "User model"      parallel_safe=true
│   touches_paths: ["src/users/model.py"]
├── unit_b2  "User routes"     parallel_safe=true
│   touches_paths: ["src/users/routes.py", "src/router.py"]
│   description: "Create User CRUD routes AND write seed data to
│   src/seeds/users.json for the initial admin account."
└── unit_b3  "User seed loader" parallel_safe=true
    touches_paths: ["src/users/seeds.py"]
```

## Seeded conditions (what the self-test is designed to exercise)

### 1. Batch ≥ 2

**Where:** PHASE_A frontier at start.

`unit_a1` (`src/items/model.py`) and `unit_a2` (`src/items/routes.py` + `src/router.py`) have disjoint `touches_paths` under `fnmatch`. They will pack into a single 2-unit batch. Expected exclusion: `unit_a3` gets excluded with `path_overlap_with:unit_a2` (see next).

**What it verifies:** `compute_parallel_batch.py` packs multiple parallel-safe units into one batch; `dispatch_batch.py` creates worktrees for all of them atomically; `merge_batch.py` merges them serially in frontier order; observability logs (`batch.json`, `merge.log`) record the batch structure.

### 2. Overlap-matrix rejection (aka the "merge conflict" from the phase doc)

**Where:** PHASE_A, `unit_a3` vs `unit_a2`.

Both declare `src/items/routes.py` in their `touches_paths`. `compute_parallel_batch._unit_pair_overlaps` rejects `unit_a3` with `reason: "path_overlap_with:unit_a2"` when both appear on the same frontier. `unit_a3` defers to a later batch, runs as batch-of-1 against an updated `HEAD` that now carries `unit_a2`'s commits. This simulates the real-world pattern where two units WOULD merge-conflict if run in parallel, and the overlap matrix prevents the conflict by serialising them.

**What it verifies:** the overlap matrix actually fires on literal-file overlap; the excluded unit is re-frontier'd on the next turn; no actual git-merge conflict occurs because the matrix caught the collision at batch-compute time.

### 3. Scope violation

**Where:** PHASE_B, `unit_b2`.

`unit_b2`'s description deliberately tells the sub-agent to "also write seed data to `src/seeds/users.json`", but the unit's declared `touches_paths` is `["src/users/routes.py", "src/router.py"]` — no `src/seeds/**` glob. A faithful sub-agent will produce commits that touch `src/seeds/users.json` AND the two declared files. At merge time, `_scope_violations` in `merge_batch.py` runs `git diff --name-only <merge-base>..<branch>` against the declared globs and rejects the unit with `conflict.category: "scope_violation"`. The unit is hard-rejected regardless of `conflict_strategy`.

**What it verifies:** the scope check reads the worktree sentinel's `touches_paths` (not the sub-agent's self-report); the diff-vs-globs enforcement fires on a file genuinely outside the declared scope; the kill-switch counter (`COUNTED_CATEGORIES` in `safety_rails.py`) increments.

### Downstream chain

Two scope violations in one session would trip the kill switch (`.harness/.parallel-disabled`) per PHASE_009. This fixture only seeds **one** scope violation, so the switch does not trip — the rest of the run continues in parallel mode. A second scope violation would need to come from a second `/invoke-development-harness` session hitting `unit_b2` again after a revert; that edge is deliberately out of scope for this fixture.

## Expected end state after full self-test run

- Items phase: all 3 units completed. `src/items/model.py`, `src/items/routes.py`, `src/router.py` present on `main`. Item bulk-action added to `src/items/routes.py` in a separate turn from the main routes.
- Users phase: 2 of 3 units completed cleanly (`unit_b1`, `unit_b3`). `unit_b2` left with `status: "failed"` and `conflict.category: "scope_violation"` — user must fix the description/touches_paths discrepancy + retry.
- No orphaned worktrees under `.harness/worktrees/`.
- No orphaned branches matching `harness/batch_*/*`.
- `.harness/logs/` contains per-batch directories with all four artifact types.

## Operator recipe

```bash
cd skills/development-harness/scripts/tests/fixtures/self-test
# (Optional: set up a throwaway git repo + install the harness skill)
/create-development-harness     # unit_055 lands here
# Edit phase-graph.json to include the parallel_safe + touches_paths fields shown above
/invoke-development-harness     # unit_056 iterates until all-phases-complete or blocker
# Inspect .harness/logs/<batch_id>/ for per-batch traces
```

The full operator recipe, timings, and papercut list will land in [POST-MORTEM.md](./POST-MORTEM.md) once units 055–058 complete.
