# Harness Checkpoint

## Last Completed
**unit_013 (PHASE_003):** Multi-file parallel-edit guidance landed in **both** invoke docs.

- [commands/invoke.md](skills/development-harness/commands/invoke.md) Step 8 gains a new `### Multi-file parallel edits` sub-section stating the **≥4 independent files** threshold, the **single assistant message, 2–3 `Agent(subagent_type: "general-purpose")`** fan-out shape, why the range is bounded at 2–3 (coordination overhead above 3; round-trip cost isn't worth it below 4), a group-by-independence rule, and two worked examples (parallel-safe: mirrored templates; NOT-parallel-safe: symbol rename with cascading callsites).
- [templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) section 9 gains a **bold-label** paragraph with the same threshold, same shape, same grouping rule, same sub-threshold fallback — compressed to the template's single-paragraph style.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_014 (PHASE_003):** Add parallel phase-review dispatch guidance to both invoke docs — during Step 10 (phase completion review), when both the `code-review` skill and `commit-agent-changes` skill are installed, dispatch them in one assistant message so they run concurrently.

## Blocked By
None.

## Evidence
- `Grep "≥4 independent files|single assistant message|2–3 \`Agent"` → matches in both files (commands/invoke.md lines 154 & 156; workspace-commands template line 93).
- `Grep 'subagent_type: "general-purpose"'` → matches in both files.
- Cross-doc consistency: identical threshold, fan-out shape, and grouping rule; command doc carries worked examples, template stays minimal.
- `python -m unittest discover skills/development-harness/scripts/tests` → 109/109 pass (docs-only change).

## Open Questions
- **Stop-hook auto-continue reliability (investigation pending this turn).** User observes the stop hook fails to auto-continue on Claude Code; hypothesis is that `continue-loop.py` was designed for Cursor's continuation protocol and Claude Code's hook contract differs fundamentally. If validated, the finding + fix will be injected via `/inject-harness-issues`.

## Tracked Issues
- **ISSUE_001** (high, open): Stop-hook portability on Windows when only `python` is on PATH. Workspace-level fix active; skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_003 PR opens after unit_015.
- **Branch:** `feat/phase-003-intra-unit-delegation`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is now 13 / `loop_budget` 12 — the stop hook will decline to continue at the end of this turn on budget grounds. That's a separate concern from the user's auto-continue investigation.

---
*Updated: 2026-04-19T22:25:00Z*
