# Harness Checkpoint

## Last Completed
**unit_bugfix_002 (PHASE_011) — ISSUE_002 RESOLVED.** Stop-hook-as-continuation-driver retired for Claude Code. Cursor installs are unchanged.

### Root cause (recap)
Claude Code's Stop hook has a **one-shot `stop_hook_active` guard** that persists for the whole session plus a **built-in loop-guard floor** on top of it. The original harness hook was a line-for-line port of the Cursor variant, which uses a `followup_message` protocol with no such guards. Outcome: on Claude Code the hook force-continued exactly once per session, then died. Users had to re-type `/invoke-development-harness` every 1–2 units.

### Four sub-edits, one commit

**(a) New [references/claude-code-continuation.md](skills/development-harness/references/claude-code-continuation.md):** documents the protocol mismatch and the two-track fix. This is where future readers chase the "why".

**(b) [templates/claude-code/hooks/continue-loop.py](skills/development-harness/templates/claude-code/hooks/continue-loop.py) rewritten to precondition-only shape:**
- Same authority chain (fleet.mode, loop_budget, blockers, open_questions, selector+checkpoint agreement).
- New `_evaluate(cwd)` returns a single-line advisory: `"proceed: <unit> in <phase>"` or `"stop: <reason>"`.
- `main()` prints the advisory, runs `_cleanup()` (sweeps `.invoke-active` + `.parallel-disabled` + `.parallel-failures.jsonl`), and **always exits 0**. No `sys.exit(2)`, no `{"decision": "block"}` JSON.
- `stop_hook_active` is read but unused — in precondition mode there is nothing to guard against.

**(c) [commands/invoke.md](skills/development-harness/commands/invoke.md) + [templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md):** both gained a **"Claude Code: run under `/loop`"** section pointing Claude Code users at `/loop /invoke-development-harness` as the autonomous-run entry point. Explicit "one batch per turn" framing for direct invocation on Claude Code. Explicit "Cursor is unchanged" reassurance.

**(d) [commands/create.md](skills/development-harness/commands/create.md) Phase 5 Claude Code branch:** preambles the JSON with the hook's new precondition-checker role description + "does NOT emit `{\"decision\": \"block\"}` or `exit(2)`" negating callout + link to the new reference doc.

**Cursor side is diff-zero.** `skills/development-harness/templates/hooks/continue-loop.py` remains canonical for Cursor; the `followup_message` path is untouched.

### Test updates
- **[test_continue_loop_claude.py](skills/development-harness/scripts/tests/test_continue_loop_claude.py) rewritten** — 9 cases across 4 classes. TestFleetModeGuard (4), TestPreconditionCheckerReachesProceed (2), TestFlagAbsentIsNoop (1), TestNonIdleBudgetAndBlockers (2). Contract flipped from `exit 2 + decision:block JSON + .invoke-active preserved` to `exit 0 + stdout advisory + .invoke-active cleaned up`.
- **New [test_claude_code_continuation_docs.py](skills/development-harness/scripts/tests/test_claude_code_continuation_docs.py)** — 12 cases across 3 classes. TestCreateDocClaudeCodeHookRole (4) pins create.md Phase 5 Claude Code branch names "precondition checker" + points at `/loop` + links claude-code-continuation.md + carries the "does NOT emit" + "always exits 0" negating callout. TestInvokeDocsLoopSection (4) pins the `Claude Code: run under /loop` heading + `/loop /invoke-development-harness` command-string + "one batch per turn" framing + "Cursor ... unchanged" reassurance across both invoke docs. TestClaudeCodeContinuationReferenceExists (4) pins the reference doc's existence + protocol-mismatch naming (`stop_hook_active`, `followup_message`) + two-track fix + Cursor-unchanged claim.
- **Pre-existing `test_safety_rails.py` TestHookStopClearsSafetyRails (2) still passes** — the `_cleanup()` helper in the new hook preserves the session-sweep contract from unit_037.

### Issue state
- [ISSUE_001.json](.harness/issues/ISSUE_001.json): resolved 2026-04-20T09:30:00Z (unit_bugfix_001).
- [ISSUE_002.json](.harness/issues/ISSUE_002.json): resolved 2026-04-20T10:15:00Z (this unit).
- [state.json](.harness/state.json) issues counter: `total: 2, open: 0, resolved: 2`.

### PHASE_008 follow-up
PHASE_008 (Stop-hook fleet-awareness, units 034–036) was scoped under the assumption that the Claude Code hook continued to drive continuation. After this fix its fleet-mode guard still applies — but now as a precondition-check advisory, not a block-continue interception. The existing tests already reflect the new shape (test_continue_loop_claude.py was updated in this unit). No additional units are required.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_045 (PHASE_011):** add a "Parallel Execution Model" section to [references/architecture.md](skills/development-harness/references/architecture.md) covering:
- Worktree-per-unit layout
- Orchestrator/sub-agent boundary
- Frontier + overlap check
- Dispatch → wait → merge lifecycle
- Conflict strategies (`abort_batch`, `serialize_conflicted`)
- When to enable / when not to

Validation: grep for section heading + structural presence test.

## Blocked By
None.

## Evidence
- [skills/development-harness/references/claude-code-continuation.md](skills/development-harness/references/claude-code-continuation.md): new 72-line doc.
- [skills/development-harness/templates/claude-code/hooks/continue-loop.py](skills/development-harness/templates/claude-code/hooks/continue-loop.py): rewrite to precondition-only shape (~130 LOC).
- [skills/development-harness/commands/invoke.md](skills/development-harness/commands/invoke.md) + [workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md): new `Claude Code: run under /loop` sections.
- [skills/development-harness/commands/create.md](skills/development-harness/commands/create.md): Phase 5 Claude Code branch preamble rewrite.
- [skills/development-harness/scripts/tests/test_continue_loop_claude.py](skills/development-harness/scripts/tests/test_continue_loop_claude.py): rewritten for precondition-only contract (9 cases).
- [skills/development-harness/scripts/tests/test_claude_code_continuation_docs.py](skills/development-harness/scripts/tests/test_claude_code_continuation_docs.py): new 180-line module, 12 cases.
- `python -m py_compile` → 0 (~0.1s) on all changed/new Python files.
- `python -m unittest skills.development-harness.scripts.tests.test_continue_loop_claude -v` → **9/9** (0.7s).
- `python -m unittest skills.development-harness.scripts.tests.test_claude_code_continuation_docs -v` → **12/12** (0.004s).
- `python -m unittest discover skills/development-harness/scripts/tests` → **243/244** + 1 OS skip in 38.7s (up from 228).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, **resolved 2026-04-20**): Windows Python-detection. Fixed in unit_bugfix_001.
- **ISSUE_002** (high, **resolved 2026-04-20**): Claude Code Stop-hook one-shot continuation. Fixed in unit_bugfix_002.

All tracked issues resolved.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_011 PR opens after the last unit closes.
- **Branch:** `feat/phase-011-documentation`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 44 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_011 progress: **2/? units done** (bugfix_001 + bugfix_002 for ISSUE_001/002). Remaining: 045 (parallel execution model doc), 046 (phase-contract updates), 047 (parallel-execution.md), 048 (unit_bugfix_001 reference — already done?).
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → 206 → 210 → 215 → 222 → 223 → 228 → **244** across phases so far.

## Batch (current or last)

Reflects `state.execution.fleet`.

- **Batch ID:** none
- **Mode:** idle

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|

### Conflicts
No conflicts.

---
*Updated: 2026-04-20T10:15:00Z*
