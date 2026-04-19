# Harness Checkpoint

## Last Completed
**unit_038 (PHASE_009):** Batch-of-1 equivalence verification locked in. The PHASE_007 rewrite collapsed the pre-existing sequential/parallel fork; unit_038 promotes that collapse from "a prose paragraph in invoke.md" into a regression-test contract.

- **Grep contract:** both [invoke.md](skills/development-harness/commands/invoke.md) (step 4 "Pick the dispatch mode") and the workspace-commands mirror [invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) gate the in-tree fast path on **`len(batch) == 1 AND config.execution_mode.parallelism.enabled == false`**. Batch-of-1 alone does NOT take a sequential path; when parallelism is on, a batch-of-1 still fans out through worktrees.
- **Integration-test half pre-satisfied** by PHASE_007 unit_033's `TestBatchOfOneDispatchModeEquivalence` in [test_invoke_rewrite.py](skills/development-harness/scripts/tests/integration/test_invoke_rewrite.py): runs the same unit through both dispatch modes on fresh fixture repos, asserts identical logical state (unit status map, evidence count, `touches_paths` files on main), and pins the substantive invariant that the in-tree path never mutates `state.execution.fleet` via a `copy.deepcopy` before/after compare.
- **New regression test:** `TestInvokeDocHasNoBatchOfOneSpecialCase` class in [test_safety_rails.py](skills/development-harness/scripts/tests/test_safety_rails.py) (3 cases). Promotes the grep-level check into a unit test so a future doc edit cannot silently reintroduce the fork:
  - `test_in_tree_gating_always_includes_parallelism_clause` — every in-tree gating line in both docs must name the `parallelism=false` clause (not batch size alone).
  - `test_no_batch_of_one_sequential_antipattern` — rejects pre-PHASE_007 phrasings like "batch-of-1 uses the sequential path" in either doc.
  - `test_batch_of_one_with_parallelism_on_goes_to_worktree` — pins the long-form invoke doc's explicit sentence that routes `len(batch) == 1` with parallelism on through worktree fan-out.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_039 (PHASE_009):** Document scope-violation always-on policy in [references/phase-contract.md](skills/development-harness/references/phase-contract.md). Policy statement: scope-violation detection (`git diff --name-only` vs merge-base + fnmatch against declared `touches_paths`) runs unconditionally regardless of `config.execution_mode.parallelism.require_touches_paths`. Rationale: `touches_paths` is a trust-boundary declaration, not a feature toggle — even when `require_touches_paths` is false, once `touches_paths` IS declared on a unit the orchestrator must enforce it because the sub-agent is untrusted. `require_touches_paths` only controls whether `compute_parallel_batch` rejects units that LACK a declaration; it does NOT relax merge-time enforcement when a declaration IS present.

## Blocked By
None.

## Evidence
- [skills/development-harness/commands/invoke.md](skills/development-harness/commands/invoke.md): step 4 "Pick the dispatch mode" gating reviewed — correct.
- [skills/development-harness/templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md): mirror verified.
- [skills/development-harness/scripts/tests/test_safety_rails.py](skills/development-harness/scripts/tests/test_safety_rails.py): new 3-case class appended; `python -m py_compile` exits 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.test_safety_rails -v` → **18/18** in 0.77s (up from 15).
- `python -m unittest discover skills/development-harness/scripts/tests` → **201/201** (up from 198) in 46.6s.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_009 PR opens after unit_040 (closes the phase).
- **Branch:** `feat/phase-009-safety-rails`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 36 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_009 progress: **2/4 units done** (037 kill switch, 038 batch-of-1 equivalence). Remaining: 039 scope-violation always-on policy docs, 040 concurrent merge serialization test.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → **201** across phases so far.

---
*Updated: 2026-04-20T06:30:00Z*
