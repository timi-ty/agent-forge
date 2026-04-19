# Harness Checkpoint

## Last Completed
**unit_009 (PHASE_002):** New [skills/development-harness/scripts/compute_parallel_batch.py](skills/development-harness/scripts/compute_parallel_batch.py) landed with stdlib-only dependencies.

- `compute_batch(frontier, parallelism)` walks the frontier left-to-right once, deterministically packing units into a batch up to `parallelism.max_concurrent_units`. A unit is dropped with `reason="not_parallel_safe"` if `parallel_safe` is false or `require_touches_paths` is true and the unit has no `touches_paths`; capacity overflow yields `reason="capacity_cap"`; overlapping paths with an already-accepted unit yield `reason="path_overlap_with:<unit_id>"`.
- `_patterns_overlap` handles three cases: literal/literal (exact match), literal/glob (`fnmatch`), glob/glob (literal-prefix containment; pessimistic -- false positives cost parallelism, never safety). `_literal_prefix` strips everything after the first `*`/`?`/`[`.
- `_parallelism_config` extracts `execution_mode.parallelism` with a v1-safe fallback: a workspace whose config.json still carries `"execution_mode": "local"` (a string) gets the defaults rather than a crash, so batching can be computed against a partially-migrated harness.
- `allow_cross_phase=False` (default) causes later-phase units in the frontier to be **deferred**, not excluded -- they remain eligible in the next batch. `allow_cross_phase=True` packs across phases in frontier order.
- `batch_id` format: `batch_YYYY-MM-DDTHH-MM-SSZ` via `_make_batch_id(now)`. Tests pin both the regex and a fixed-`datetime` assertion.

CLI surface (`--input <frontier.json>` `--config <config.json>` `[--root]`) emits `{batch_id, batch, excluded}` on stdout. `--help` is covered by the smoke suite.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_010 (PHASE_002):** Add one dedicated regression test per exclusion reason ( `not_parallel_safe`, `path_overlap_with:<unit_id>`, `capacity_cap` ) on a crafted input. The three reasons are already covered indirectly by unit_009's `TestComputeBatch`, but unit_010 requires a named test per reason so a future selector refactor can't silently drop one of them.

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/compute_parallel_batch.py](skills/development-harness/scripts/compute_parallel_batch.py): new module (228 LOC incl. docstring).
- [skills/development-harness/scripts/tests/test_compute_parallel_batch.py](skills/development-harness/scripts/tests/test_compute_parallel_batch.py): 23 cases across 5 test classes.
- `python -m unittest discover skills/development-harness/scripts/tests` -> 106/106 pass (up from 83 at end of unit_008).
- `python skills/development-harness/scripts/compute_parallel_batch.py --help` prints usage (covered by `TestCliSmoke.test_cli_help_runs`).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Stop-hook portability on Windows when only `python` is on PATH. Workspace-level fix active; stop hook auto-continued from unit_008 -> unit_009 in this session. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_002 PR opens after unit_010.
- **Branch:** `feat/phase-002-frontier-selector`.
- **Merge:** squash; autonomous.

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `loop_budget` was bumped from 10 to 12 in state.json; revisit as a proper config knob in PHASE_011's doc pass.

---
*Updated: 2026-04-19T20:45:00Z*
