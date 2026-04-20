# Wall-clock comparison — Tasklet self-test fixture

Captured by `test_self_test_run.TestWallClockParallelVsSequential.test_parallel_vs_sequential_produces_comparable_table` on a fresh run against the fixture in [phase-graph.json](./phase-graph.json). Both runs use worktree fan-out (dispatch + merge) so the only independent variable is `max_concurrent_units`.

| Run | max_concurrent_units | Turns | Batch sizes | Wall-clock (s) |
|-----|----------------------|-------|-------------|----------------|
| Parallel   | 3 | 3 | [2, 1, 3] | 2.05 |
| Sequential | 1 | 6 | [1, 1, 1, 1, 1, 1] | 2.02 |

## Ratio

Sequential / Parallel wall-clock ratio: **0.98x**. The parallel run completes in 3 turn(s) versus 6 for sequential. On this fixture the batching savings come from Turn 1 packing unit_a1 + unit_a2 and Turn 3 packing the full PHASE_B set (b1 + b2 + b3 before b2's scope-violation rejection). A real project with slower per-unit work (real test runs, not fake-commits) will see a larger ratio because the fixed overhead (worktree add + merge) is unchanged while the per-unit work overlaps.

## Orphan check

Both runs leave only `unit_b2`'s worktree alive -- the scope-violation path in `merge_batch.py` preserves it so a human can inspect and repair. All other worktrees are torn down; no residual `harness/batch_*/*` branches remain.
