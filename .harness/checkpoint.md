# Harness Checkpoint

## Last Completed
**unit_010 (PHASE_002):** Dedicated exclusion-reason regression tests landed in [test_compute_parallel_batch.py](skills/development-harness/scripts/tests/test_compute_parallel_batch.py).

- New `TestExclusionReasons` class: one test per machine-readable reason string, each on the narrowest crafted input that can only trigger that one reason.
  - `test_reason_not_parallel_safe_fires` — single unit with `parallel_safe=False`; asserts `{unit_id:"solo", reason:"not_parallel_safe"}`.
  - `test_reason_path_overlap_with_fires` — u1=`src/shared/**` vs u2=`src/shared/auth.ts`; asserts `{unit_id:"loser", reason:"path_overlap_with:winner"}` (pins the `<unit_id>` suffix).
  - `test_reason_capacity_cap_fires` — two disjoint units with `max_concurrent_units=1`; asserts `{unit_id:"u2", reason:"capacity_cap"}`.
- Test names embed each reason literal so a future refactor that drops or renames a constant surfaces as a named failure rather than a silent regression.
- Module docstring updated to describe the unit_009 vs unit_010 split.

With unit_010 done, **all four PHASE_002 units are complete** and the frontier selector / batch computer are ready to be consumed by PHASE_005 and PHASE_007.

## What Failed (if anything)
None.

## What Is Next
**Phase completion review for PHASE_002.** Run `pr-review-checklist.md` end-to-end, invoke the `code-review` skill on the PHASE_002 PR, mark PHASE_002 `"completed"` in [phase-graph.json](.harness/phase-graph.json) once the review is green, then autonomous squash-merge per [harness-git.md](.claude/rules/harness-git.md). After merge, PHASE_003 (unit_011) is the next head.

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/tests/test_compute_parallel_batch.py](skills/development-harness/scripts/tests/test_compute_parallel_batch.py): `+69 / -2` to add `TestExclusionReasons` and refresh the module docstring.
- `python -m unittest skills.development-harness.scripts.tests.test_compute_parallel_batch -v` → 26/26 pass (up from 23; three new `TestExclusionReasons` cases).
- `python -m unittest discover skills/development-harness/scripts/tests` → 109/109 pass (up from 106).
- `python -m py_compile skills/development-harness/scripts/compute_parallel_batch.py skills/development-harness/scripts/tests/test_compute_parallel_batch.py` → no output (Layer 1 clean).
- `python .harness/scripts/select_next_unit.py` → `phase_complete: true`, next `PHASE_003 / unit_011`.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Stop-hook portability on Windows when only `python` is on PATH. Workspace-level fix active; skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_002 PR opens now with all four units plus the phase-graph completion stamp.
- **Branch:** `feat/phase-002-frontier-selector`.
- **Merge:** squash; autonomous.

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `loop_budget` was bumped from 10 to 12 in state.json; revisit as a proper config knob in PHASE_011's doc pass.

---
*Updated: 2026-04-19T21:15:00Z*
