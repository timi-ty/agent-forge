# Harness Checkpoint

## Last Completed
**unit_007 (PHASE_002):** Rewrote [skills/development-harness/scripts/select_next_unit.py](skills/development-harness/scripts/select_next_unit.py) around a new `compute_frontier(phases, max_items=None)` function. A unit enters the frontier only when its phase's `depends_on` are all `completed`, its own `depends_on` are all `completed`, and it is not itself `completed`. Ordering is phase-list then unit-list -- deterministic.

CLI surface:

- **No-flag call** preserves the v1 stop-hook JSON contract: `{ found, phase_id, phase_slug, unit_id, unit_description, phase_complete, all_complete }`. `phase_complete` is reinstated via a separate `_phase_completion_pending` helper so the invoke flow still gets the "run phase-completion review" signal.
- **`--frontier`** emits the full frontier as a JSON array with every v2 unit field (`phase_id`, `phase_slug`, `id`, `description`, `status`, `depends_on`, `touches_paths`, `parallel_safe`). Consumed by the PHASE_002 batcher and the PHASE_007 invoke rewrite.
- **`--max N`** truncates the frontier at N entries.

There is **no legacy list-order fallback**. A unit missing `depends_on` (or with a non-list `depends_on`) raises `MalformedPhaseGraph` and the CLI exits 2 with the message `Run validate_harness.py -- the graph is not v2-conformant`. A smoke run of the new skill selector against this workspace's (still-v1-shaped) phase-graph confirmed this.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_008 (PHASE_002):** Expand frontier resolution coverage -- linear, diamond, disconnected, and partially-completed graph topologies -- and lock in the "error loudly on malformed units" stance with explicit test cases beyond the two already added in unit_007.

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/select_next_unit.py](skills/development-harness/scripts/select_next_unit.py): `compute_frontier`, `select_next_unit`, `_phase_completion_pending`, `_assert_unit_shape`, `MalformedPhaseGraph`; `--frontier` and `--max N` wired through `main`.
- [test_select_next_unit.py](skills/development-harness/scripts/tests/test_select_next_unit.py): existing fixtures upgraded to v2 shape; `TestFrontierFlag` (4 cases) and `TestNoLegacyFallback` (2 cases) added.
- `python -m unittest discover skills/development-harness/scripts/tests` -> 71/71 pass (up from 65 at the end of PHASE_001).
- Frozen `.harness/scripts/select_next_unit.py` is untouched, so the running stop hook on this workspace keeps using the v1 logic.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Stop-hook portability on Windows when only `python` is on PATH. Workspace-level fix is active (stop-hook auto-continuation works in this session). Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase (PHASE_001 merged; PHASE_002 PR opens after unit_010).
- **Branch:** `feat/phase-002-frontier-selector` (cut from `main` after PHASE_001's squash-merge).
- **Merge:** squash; autonomous per the updated harness-git rule.

## Reminders
- Skill edits only go to `skills/development-harness/**`. `.harness/scripts/` is a frozen runtime copy.
- Parallelism stays off in this bootstrap's config until PHASE_007 lands.

---
*Updated: 2026-04-19T18:15:00Z*
