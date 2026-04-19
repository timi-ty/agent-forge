# Harness Checkpoint

## Last Completed
**unit_004 (PHASE_001):** Registered `.harness/worktrees/` and `.harness/logs/` in `skills/development-harness/schemas/manifest.json` (both harness-owned transient directories) and updated the `.gitignore` template description in `commands/create.md`. Also hardened this workspace's own `.harness/.gitignore` with the same entries plus `.parallel-disabled` and `.lock` for the later phases.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_005:** Bump `SCHEMA_VERSION` in `skills/development-harness/scripts/harness_utils.py` from `"1.0"` to `"2.0"` and update `check_schema_version` to emit an actionable "re-run `/create-development-harness`" error on mismatch.

## Blocked By
None.

## Evidence
- `skills/development-harness/schemas/manifest.json`: two new entries for `worktrees/` and `logs/` with notes.
- `skills/development-harness/commands/create.md`: `.gitignore` template description now mentions `worktrees/` and `logs/`.
- `.harness/.gitignore` (this workspace) extended with `worktrees/`, `logs/`, `.parallel-disabled`, `.lock`.
- `python -m unittest discover skills/development-harness/scripts/tests` → 36/36 tests pass.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows stop-hook portability — shebang `env python3` fails when only `python` is on PATH. Workspace-level fix committed (`c3e2428`). Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011's unit list (to land before the rest of PHASE_011's documentation work).

## Commit Policy (recorded)
- **PR cadence:** one PR per phase (13 PRs total).
- **Bootstrap commit:** separate `chore(harness): bootstrap` commit first on the phase branch, then unit commits follow.
- **Branch:** `feat/phase-001-schema-and-data-model` (cut from `main`).
- **PR open:** only when the phase's last unit completes (unit_006 for PHASE_001).
- **Push:** not until PR open.

## Reminders
- All skill edits go to `skills/development-harness/**`. `.harness/scripts/` is a frozen runtime copy.
- Parallelism stays off in this bootstrap's config until PHASE_007 lands.
- Stop-hook loop does not auto-continue in this Claude Code session (ISSUE_001 workspace fix would take effect in a new session). Manual `/invoke-development-harness` required between units for this session.

---
*Updated: 2026-04-19T00:30:00Z*
