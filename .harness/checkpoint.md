# Harness Checkpoint

## Last Completed
**PHASE_002 (all four units):** Frontier selector and batch computation landed and merged (pending squash).

- **unit_007** — [select_next_unit.py](skills/development-harness/scripts/select_next_unit.py) rewritten around `compute_frontier(phases, max_items)`; `--frontier` and `--max N` flags added; no-flag call preserves the v1 stop-hook JSON contract; `MalformedPhaseGraph` (exit 2) replaces the legacy list-order fallback.
- **unit_008** — `TestFrontierTopologies` locks the frontier contract on linear, diamond, disconnected, partially-completed, and phase-complete-pending graphs; `TestNoLegacyFallback` expanded to four malformed-unit cases (missing `depends_on`, non-list `depends_on`, non-dict unit, missing `id`).
- **unit_009** — [compute_parallel_batch.py](skills/development-harness/scripts/compute_parallel_batch.py): stdlib-only greedy pack with `fnmatch` + literal-prefix glob-overlap matrix, `_parallelism_config` with v1-safe fallback, UTC-timestamped `batch_id`, CLI (`--input`, `--config`, `--root`).
- **unit_010** — `TestExclusionReasons` pins each machine-readable reason (`not_parallel_safe`, `path_overlap_with:<unit_id>`, `capacity_cap`) on the narrowest crafted input, with test names embedding the reason literal so a dropped/renamed constant surfaces as a named failure.

Phase completion review ran the `code-review` skill against PR #26 and cleared the phase with two Low findings (unused `import re`, unused `root` parameter); both addressed in a follow-up commit on the same branch.

## What Failed (if anything)
None.

## What Is Next
**PHASE_003, unit_011** — Insert an Exploration step in [skills/development-harness/commands/invoke.md](skills/development-harness/commands/invoke.md) that dispatches `Agent(Explore)` for refactor / extend / fix / migrate / update keywords before implementation. New branch off main after PR #26 merges.

## Blocked By
None.

## Evidence
- `python -m unittest discover skills/development-harness/scripts/tests` → 109/109 pass (PHASE_001 end: 65 → PHASE_002 end: 109).
- PR #26 at https://github.com/timi-ty/agent-forge/pull/26: 8 commits across 7 files, +1483 / -243.
- Code-review report: [pr-26-review.md](pr-26-review.md) (zero High, zero Medium, two Low — both fixed).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Stop-hook portability on Windows when only `python` is on PATH. Workspace-level fix active; skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_002 → PR #26 (squash-merge pending).
- **Branch:** `feat/phase-002-frontier-selector` (delete on merge).
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `loop_budget` was bumped from 10 to 12 in state.json; revisit as a proper config knob in PHASE_011's doc pass.

---
*Updated: 2026-04-19T21:30:00Z*
