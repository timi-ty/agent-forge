# Harness Checkpoint

## Last Completed
**PHASE_007 complete (all 5 units).** The parallel-execution substrate that PHASE_005 + PHASE_006 built now has a live contract in the live invoke flow, validated end-to-end by a new integration test.

- **unit_029** — [commands/invoke.md](skills/development-harness/commands/invoke.md) whole-file rewrite, 432 → 332 LOC. Zero "sequential path / parallel path" fork language. 12-step batch-driven pipeline (0–11); Steps 5 and 6 are the only branches (in-tree fast path vs worktree fan-out); Steps 0–3 and 7–11 converge.
- **unit_030** — [workspace-commands template](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) mirror in the compact-template style (121 LOC).
- **unit_031** — [architecture.md Batch Semantics subsection](skills/development-harness/references/architecture.md#L81-L89) making the one-turn-one-batch semantics explicit (`session_count` increments once per turn; full fleet transition completes within one turn).
- **unit_032** — parallel phase-review dispatch (pre-satisfied by 029+030's Step 10 rewrites; grep-verified).
- **unit_033** — new [tests/integration/test_invoke_rewrite.py](skills/development-harness/scripts/tests/integration/test_invoke_rewrite.py) with **two test classes**:
  - `TestThreeUnitParallelBatch` — 3 disjoint-file units with `parallelism.enabled=true` complete in **one** `compute_batch → dispatch_batch → fake agents → merge_batch` cycle. Asserts phase-graph entries flip to `completed` with evidence, `fleet.mode == "idle"` at end of turn, all files land on `main`, zero residual worktrees/branches.
  - `TestBatchOfOneDispatchModeEquivalence` — same single unit executed two ways (in-tree fast path vs worktree fan-out) on fresh fixture repos. Compares logical state (status + evidence count + files-on-main) via a helper; asserts strict equality. SHAs differ by design; logical state must not.

**Test-suite growth this phase:** 171 → **173** (+2 integration cases). The integration test is the first that starts from a realistic phase-graph dict and exercises `compute_frontier + compute_parallel_batch.compute_batch + dispatch_batch + merge_batch` together — it catches regressions the PHASE_005 test_parallel_invoke.py misses because that one starts from a hand-crafted fleet state.

## What Failed (if anything)
None.

## What Is Next
**Run PHASE_007 phase completion review**, open the phase PR, autonomous squash-merge per [harness-git.md](.claude/rules/harness-git.md). After merge, advance to **unit_034 (PHASE_008, stop-hook fleet-awareness)** — update `continue-loop.py` to stop when `state.execution.fleet.mode != "idle"` and delete `.invoke-active` on stop.

**Caveat for PHASE_008 in light of ISSUE_002:** The Stop hook is a one-shot continuation primitive on Claude Code (hence `/loop` driving this session). PHASE_008's unit scopes assume the hook keeps driving continuation, but `unit_bugfix_002` (head of PHASE_011) will retire that role for Claude Code. PHASE_008's fleet-awareness is still valuable as a **precondition gate** (stop when fleet isn't idle), so the unit scopes likely don't need re-writing — just a clarifying note that the hook's role on Claude Code is check-and-advise, not continue-driver. Worth revisiting at PHASE_008's opening turn; no action needed now.

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/tests/integration/test_invoke_rewrite.py](skills/development-harness/scripts/tests/integration/test_invoke_rewrite.py): new 288-line integration module, 2 cases.
- `python -m py_compile` → 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.integration.test_invoke_rewrite -v` → 2/2 (3.5s).
- `python -m unittest discover skills/development-harness/scripts/tests` → **173/173** (up from 171 at end of PHASE_006) in 45.0s.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot. Both invoke docs point Claude Code users at `/loop /invoke-development-harness`; full fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_007 PR opens now with all five units.
- **Branch:** `feat/phase-007-invoke-rewrite` (delete on merge).
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 32 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE progress so far: PHASE_001–007 complete (33 units). Remaining: PHASE_008–013 (≈25 units).
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → **173** across phases so far.

---
*Updated: 2026-04-20T04:50:00Z*
