# PHASE_008: Stop-Hook Fleet Awareness

## Objective
Make the stop hook safe under parallel execution. A turn that crashed mid-batch must not trigger loop continuation into an inconsistent state.

## Why This Phase Exists
Today the hook inspects `state.execution` for pointers and decides whether to continue. Under parallel execution, a crash between `dispatch_batch.py` and `merge_batch.py` leaves `state.fleet.mode != "idle"`. If the hook continues in that state, the next turn has no coherent "next unit" to work on — worktrees exist, branches exist, but the invoke flow would try to start a new batch. Stopping and requiring `/sync-development-harness` is the right recovery.

## Scope
- Update `skills/development-harness/templates/claude-code/hooks/continue-loop.py`: insert a pre-check — if `state.execution.fleet.mode != "idle"`, exit 0 (stop) after deleting `.invoke-active`.
- Mirror in `skills/development-harness/templates/hooks/continue-loop.py` (Cursor variant): same pre-check; return `{}` to stop.
- Unit tests: simulated `fleet.mode == "dispatched"` triggers stop; `fleet.mode == "idle"` preserves existing behavior; absence of `fleet` block (v1-style state) treated as `idle`.
- Manual verification checklist: kill an invoke turn mid-batch, then start a new session and confirm the hook stops immediately; `/sync-development-harness` detects the orphan.

> ⚠️ **Edit target:** `skills/development-harness/templates/**` only.

## Non-goals
- Automated orphan cleanup on hook stop — handled by `/sync` on user initiative.
- Redesigning the rest of the authority chain — unchanged.

## Dependencies
- PHASE_001 (`fleet.mode` field exists).
- PHASE_007 (the invoke flow that would set `fleet.mode`).

## User-visible Outcomes
- A crashed mid-batch turn stops the loop cleanly on the next invocation.
- The user's path to recovery is unambiguous: `/sync-development-harness` → `/invoke-development-harness`.

## Units of Work

| ID | Description | Acceptance Criteria | Validation Method | Status |
|----|-------------|--------------------|--------------------|--------|
| unit_034 | Claude Code `continue-loop.py` — `fleet.mode != "idle"` → stop | Pre-check present; `.invoke-active` removed on stop; missing `fleet` block treated as idle | `python -m unittest skills.development-harness.scripts.tests.test_continue_loop_claude` | pending |
| unit_035 | Cursor `continue-loop.py` — same guard | Identical logic ported to the Cursor hook protocol | `python -m unittest skills.development-harness.scripts.tests.test_continue_loop_cursor` | pending |
| unit_036 | Manual verification: mid-batch kill → orphan surfaces via `/sync` | Documented checklist captured in this phase's rollback section | checklist executed | pending |

## Validation Gates
- **Layer 1:** Python syntax valid.
- **Layer 2:** Hook unit tests pass for both Claude Code and Cursor shapes.

## Deployment Implications
Not deploy-affecting.

## Completion Evidence Required
- `test_continue_loop_claude` and `test_continue_loop_cursor` exit 0.
- Manual checklist run and recorded.

## Rollback / Failure Considerations
Hook scripts only. If the guard breaks the hook, the invoke loop simply stops more often — annoying but not dangerous. Revert on failure.

### Manual verification checklist (unit_036)

The fleet-mode guard's unit tests cover the observable contract (exit code + `.invoke-active` presence across `dispatched` / `merging` / `idle` / missing-fleet cases + a positive control proving idle doesn't short-circuit). The following manual steps complement the automated tests by exercising the crash-recovery path with a real workspace harness:

- [ ] **Set up a live invoke session.** Run `/invoke-development-harness` once on a workspace with `config.execution_mode.parallelism.enabled == true` and at least one pending multi-unit phase. Watch for `state.execution.fleet.mode` flipping to `"dispatched"` when `dispatch_batch.py` runs during Step 5.
- [ ] **Kill the turn mid-batch.** Interrupt (Ctrl+C or force-quit the agent session) after `fleet.mode == "dispatched"` but before `merge_batch.py` runs. On disk: `.harness/.invoke-active` should still exist; `.harness/state.json` should show `fleet.mode == "dispatched"`; per-unit worktrees are still in `.harness/worktrees/<batch_id>/`.
- [ ] **Start a new session in the same workspace.** Trigger the stop hook (start any session — it doesn't need to be `/invoke-development-harness`).
- [ ] **Confirm the guard fires.** The hook should exit 0 / print `{}` (Cursor) — the loop does not auto-continue. `.harness/.invoke-active` is now removed.
- [ ] **Run `/sync-development-harness`.** It should surface the orphan under `state.drift.divergences` — an `orphan_worktree` for each per-unit dir and (optionally) an `orphan_branch` for each `harness/<batch_id>/*` branch.
- [ ] **Recover.** Run `teardown_batch.py --batch-id <batch_id>` to clean up, or resolve the half-done work manually. Re-run `/sync` to confirm the divergences are gone. Then `/invoke-development-harness` restarts cleanly.

If any step above behaves differently, the fleet-mode guard or the sync-detection is wrong — revert and investigate before merging into a production harness.

## Status
pending
