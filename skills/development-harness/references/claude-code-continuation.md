# Claude Code Continuation Model

The development-harness skill's Cursor implementation uses a Stop-hook-driven continuation loop: after every completed unit, the hook emits a `followup_message` and Cursor re-invokes the agent autonomously. On Claude Code, the same approach **does not work** — this document explains why and records the fix (ISSUE_002).

## The protocol mismatch

**Cursor Stop hook protocol:**
- Hook returns `{"followup_message": "..."}` → Cursor starts a new turn with that message.
- Hook returns `{}` → session stops cleanly.
- No per-session guard. The hook may force-continue as many times as it wants in the same session.
- The harness's own `loop_budget` (in `.harness/state.json`) is therefore the only cap.

**Claude Code Stop hook protocol:**
- Hook exits `2` with stdout `{"decision": "block", "reason": "..."}` → Claude Code blocks the stop and continues the turn.
- Hook exits `0` → session stops cleanly.
- **One-shot guard.** After the first hook-driven block-continue in a session, Claude Code sets `stop_hook_active: true` on every subsequent Stop event. The hook cannot reset this flag; it persists for the entire session.
- **Loop-guard floor.** Even if a hook tries to bypass `stop_hook_active`, Claude Code's built-in loop detector will force a stop after a small number of consecutive block-continues. There is no documented opt-out.

The two protocols look superficially identical (hook returns a signal, host decides what to do). They are structurally opposite: Cursor gives the skill author continuation authority, Claude Code explicitly withholds it.

## What the original (broken) port did

The Claude Code variant of `continue-loop.py` was a line-for-line port of the Cursor variant. Its authority chain (budget, blockers, open_questions, selector-vs-checkpoint agreement) ran correctly, but when all checks passed it emitted:

```python
print(json.dumps({"decision": "block", "reason": message}))
sys.exit(2)
```

This worked for **exactly one** unit. After that, `stop_hook_active` was `true` and the hook's own early-return at `if input_data.get("stop_hook_active", False): _stop(cwd)` respected the one-shot guard by design — the session stopped, and the user had to type `/invoke-development-harness` again by hand.

## The fix: two tracks by protocol

### Cursor: unchanged
`skills/development-harness/templates/hooks/continue-loop.py` stays the canonical driver. Its `followup_message` path is the autonomous-run primitive on Cursor. This doc does not affect Cursor.

### Claude Code: retire the block-continue driver, use `/loop` instead
1. `skills/development-harness/templates/claude-code/hooks/continue-loop.py` is rewritten to a **precondition-only** shape. It runs the same authority chain as before, but:
   - Always exits `0`. No `exit(2)`, no `{"decision": "block"}`.
   - Prints an advisory to stdout describing the next unit (when preconditions are met) or the reason to stop (when they aren't).
   - Cleans up session flags (`.invoke-active`, `.parallel-disabled`, `.parallel-failures.jsonl`) on every path, because the session is going to stop regardless.

2. Autonomous multi-turn runs use Claude Code's native `/loop` skill (a March 2026 primitive that schedules a prompt to re-fire at a configurable cadence or event). The idiomatic usage is:
   ```
   /loop /invoke-development-harness
   ```
   `/loop` fires `/invoke-development-harness` now, then re-fires on its schedule. Each firing is a fresh session, so `stop_hook_active` never has a chance to accumulate.

3. The harness's own `loop_budget` in `state.json` remains the cap. It is enforced inside the invoke skill (before the unit runs) and by the Stop-hook's precondition check (which will now advise "budget exhausted" instead of force-continuing).

### Why not just remove `stop_hook_active` from the hook?

The hook could try to ignore the flag, but Claude Code's loop-guard floor kicks in after ~2–3 consecutive block-continues and stops anyway. The upshot is identical: you get one or two continuations, then you stop. Removing the check buys one turn and trades away clarity. Retiring the driver role entirely is cleaner.

## Regression guards

Three test shapes cover the fix (ISSUE_002 `regression_coverage` field):

1. **Docs-linter (`commands/create.md`).** The Claude Code branch of Phase 5 must describe the hook as a **precondition checker**, not a block-continue driver. The pre-fix language ("block stopping and continue") must not reappear.
2. **Docs-linter (`commands/invoke.md` + `templates/workspace-commands/invoke-development-harness.md`).** Both docs must carry a "Claude Code: run under `/loop`" section pointing Claude Code users at `/loop /invoke-development-harness` as the autonomous-run entry point.
3. **Unit test of the hook's new mode.** Flag-present + preconditions-met → exit 0 with an advisory that names the next unit. Flag-present + preconditions-failed → exit 0 with a blocker advisory. Flag-absent → exit 0 silently (the hook is a no-op outside harness invoke sessions).

## Follow-up: PHASE_008 scope

`PHASE_008` (Stop-hook fleet-awareness, units 034–036) was scoped under the assumption that the Claude Code hook continued to drive continuation. After this fix, its fleet-mode guard still applies — but as a precondition-check that advises "fleet.mode != idle; run /sync-development-harness" rather than a block-continue interception. The existing PHASE_008 tests (`test_continue_loop_claude.py`, `test_continue_loop_cursor.py`) need to be updated for the new exit-0-plus-advisory shape on the Claude Code side; the Cursor side is untouched.
