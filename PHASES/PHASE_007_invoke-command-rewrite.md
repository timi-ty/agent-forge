# PHASE_007: Invoke Command Rewrite

## Objective
Collapse the invoke flow into a single batch-driven pipeline. Batch size 1 runs in-tree (no worktree), batch size N fans out to sub-agents — but both traverse the same dispatch → execute → verify → merge → state → commit checkpoints. No forked code path.

## Why This Phase Exists
The existing invoke command assumes one unit per turn. A "sequential path vs parallel path" fork introduces two sets of failure modes, two sets of logs, and two sets of tests. A unified flow where a batch of 1 is just a trivial batch keeps the mental model, testing, and observability cohesive.

## Scope
- Rewrite `skills/development-harness/commands/invoke.md` as a single flow:
  - Step 0–3: unchanged (tool detection, invoke flag, validate, load state).
  - Step 4: compute batch via `compute_parallel_batch.py`. Output is always a batch object; size may be 1 or N.
  - Step 5 — dispatch:
    - If batch size == 1 and `parallelism.enabled == false`: skip worktree setup; current working tree is the "worktree" for this single unit. `state.fleet.mode = "idle"` remains.
    - Otherwise: run `dispatch_batch.py` — creates per-unit worktrees, fan-out briefings, `state.fleet.mode = "dispatched"`.
  - Step 6 — execute:
    - In-tree case: execute the unit inline (current behavior).
    - Fan-out case: emit one `Agent(subagent_type: "harness-unit")` tool call per unit in a single assistant message; each sub-agent gets its worktree path, phase excerpt, unit row, rules, and expected report schema.
  - Step 7 — verify: for every resulting diff, run scope-violation check; force `failed` on any violation regardless of sub-agent self-report. For the in-tree case, scope-violation check diffs the working tree against declared `touches_paths`.
  - Step 8 — merge: `merge_batch.py` (no-op for in-tree single-unit; actual merges for worktree batches). `state.fleet.mode = "merging"` during, then back to `"idle"`.
  - Step 9 — state: update `state.json` (completed units → `completed`; failed/conflicted → `pending` with blockers) and `checkpoint.md`. `checkpoint.next_action` is populated via `select_next_unit.py` (no-flag mode) so the stop hook's agreement check keeps working.
  - Step 10 (commit) and Step 11 (turn ends) unchanged.
- Mirror in `skills/development-harness/templates/workspace-commands/invoke-development-harness.md`.
- Document in `skills/development-harness/references/architecture.md`: one turn = one batch; `session_count` increments once per turn regardless of batch size.
- Wire parallel phase-review dispatch (code-review skill concurrent with commit-agent-changes) into the rewritten flow.

> ⚠️ **Edit target:** `skills/development-harness/**` only. This phase changes the invoke flow — the next bootstrap will generate the updated copy in `.harness/`.

## Non-goals
- Stop-hook fleet awareness — PHASE_008.
- Safety-rail policy (kill switch, auto-downgrade) — PHASE_009.
- Observability artifacts beyond what `state.fleet` already captures — PHASE_010.

## Dependencies
- PHASE_005 (dispatch/merge/teardown scripts).
- PHASE_006 (harness-unit agent definition + core rules).

## User-visible Outcomes
- A single invoke turn completes a whole batch (size 1 or N) end-to-end.
- Reading the updated invoke doc, an agent executes the same state transitions regardless of parallelism.
- Fixture integration test completes a 3-unit parallel phase in one turn.

## Units of Work

| ID | Description | Acceptance Criteria | Validation Method | Status |
|----|-------------|--------------------|--------------------|--------|
| unit_029 | Rewrite `commands/invoke.md` into a single batch-driven flow with in-tree fast path for batch-of-1 | Doc has no "sequential path / parallel path" branch; every step applies to both batch sizes; `state.fleet.mode` transitions documented | self-review checklist + grep to confirm no "sequential path" branch language remains | pending |
| unit_030 | Mirror in `templates/workspace-commands/invoke-development-harness.md` | Wording consistent; same step numbering; same transitions | self-review + grep | pending |
| unit_031 | Document one-turn-per-batch semantics in `references/architecture.md` | New paragraph stating `session_count` increments once per turn; links to PHASE_007 rewrite rationale | grep | pending |
| unit_032 | Wire parallel phase-review dispatch (code-review + commit-agent-changes in one assistant message) | Phase completion review step in both docs explicitly says "single assistant message with both Agent calls" | grep | pending |
| unit_033 | End-to-end integration test: 3-unit fixture parallel phase completes in one turn; batch-of-1 in-tree produces the same final state as a batch-of-1 worktree would | Test exits 0; final phase-graph shows all units completed with evidence; state.fleet.mode == "idle" | `python -m unittest skills.development-harness.scripts.tests.integration.test_invoke_rewrite` | pending |

## Validation Gates
- **Layer 1:** Markdown parses.
- **Layer 2:** Integration test passes.
- **Layer 3:** Manual dry-read — the rewritten doc is executable by a cold agent.

## Deployment Implications
Not deploy-affecting.

## Completion Evidence Required
- `test_invoke_rewrite` integration test exits 0.
- Grep confirms no residual "sequential path" language in either invoke doc.
- Grep confirms the parallel phase-review dispatch block in both docs.
- `references/architecture.md` contains the one-turn-per-batch paragraph.

## Rollback / Failure Considerations
The live harness is still running against the frozen v1 invoke docs at `.harness/` (indirectly, via `.claude/commands/invoke-development-harness.md`). Failure in this phase affects only the skill source. On failure, revert the phase commits; the running harness is unaffected until the next bootstrap.

## Status
pending
