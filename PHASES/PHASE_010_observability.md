# PHASE_010: Observability

## Objective
Make fleet state, per-batch execution, and post-merge validation legible to humans without reading JSON.

## Why This Phase Exists
Parallel execution multiplies the surface area of what's happening at any moment. Without per-batch logs and structured state rendering, users (and debugging agents) have to piece together what went wrong from git history and commit messages. A dedicated `.harness/logs/<batch_id>/` tree and a fleet-aware state command make post-hoc inspection tractable.

## Scope
- Extend `skills/development-harness/templates/checkpoint-template.md` with a "Batch" section: batch ID, mode, per-unit status and branch, conflicts summary.
- Update `skills/development-harness/commands/state.md` and `skills/development-harness/templates/workspace-commands/harness-state.md` to render:
  - Fleet status from `state.execution.fleet`.
  - Orphaned worktrees via `sync_harness.py --dry-run`.
  - Per-batch timings (dispatch start, merge complete, total wall-clock).
- Orchestrator writes to `.harness/logs/<batch_id>/` during each parallel turn:
  - `batch.json` — the full batch plan + overlap analysis from `compute_parallel_batch.py`.
  - `<unit_id>.md` — the sub-agent's markdown summary (written by the sub-agent itself, per the harness-unit contract).
  - `merge.log` — output from `merge_batch.py`.
  - `validation.log` — post-merge validation output.
- Logs are harness-owned and gitignored. Retained until `/clear` or an explicit log-prune command (future).

> ⚠️ **Edit target:** `skills/development-harness/**` only. The log directory creation logic lives inside `merge_batch.py` / `dispatch_batch.py` (modified here).

## Non-goals
- Time-based log pruning — out of scope; manual cleanup via `/clear` for now.
- Central aggregation, remote log shipping — out of scope.
- Real-time streaming of sub-agent output — sub-agents emit their summaries at the end.

## Dependencies
- PHASE_005 (dispatch + merge scripts that write the logs).
- PHASE_007 (invoke flow that orchestrates the batch lifecycle).

## User-visible Outcomes
- `/harness-state` shows current batch status, orphaned worktrees, and recent batch timings.
- `.harness/logs/<batch_id>/` exists for every completed batch with all four artifacts.
- Checkpoint file includes a Batch section when a batch is in flight or was the last thing to complete.

## Units of Work

| ID | Description | Acceptance Criteria | Validation Method | Status |
|----|-------------|--------------------|--------------------|--------|
| unit_041 | Extend `templates/checkpoint-template.md` with Batch section | New section present with ID, mode, units, conflicts placeholders | grep | pending |
| unit_042 | Update `commands/state.md` + workspace-command template to render fleet + orphans + timings | Both docs instruct rendering these three areas; output format specified | self-review + grep | pending |
| unit_043 | Log directory creation logic in orchestrator scripts | `.harness/logs/<batch_id>/` created by `dispatch_batch.py`; all four artifacts written across dispatch/merge; gitignored | `python -m unittest skills.development-harness.scripts.tests.test_batch_logs` | pending |
| unit_044 | Integration: sample batch produces all log artifacts | Integration test runs a batch and asserts presence and non-empty content of each artifact | extend `test_parallel_invoke.py` with log-artifact assertions | pending |

## Validation Gates
- **Layer 1:** Markdown + Python syntax valid.
- **Layer 2:** `test_batch_logs` passes.
- **Layer 3:** Integration test with log assertions passes.

## Deployment Implications
Not deploy-affecting.

## Completion Evidence Required
- `test_batch_logs` exits 0.
- Integration test with log assertions exits 0.
- Manual spot check: a real run produces `.harness/logs/<batch_id>/{batch.json, <unit>.md, merge.log, validation.log}`.

## Rollback / Failure Considerations
Logs are additive and isolated. A failure in log writing should not cascade — wrap log writes in try/except so merge is not blocked by log-dir issues. Revert on test failure.

## Status
pending
