# Harness Checkpoint

## Last Completed
**unit_bugfix_001 (PHASE_011) — ISSUE_001 RESOLVED.** Windows Python-detection bug in `create.md` Phase 5 Hook configuration fixed at the skill source.

### The fix
[commands/create.md](skills/development-harness/commands/create.md) Phase 5 "Hook configuration" subsection now:

1. **Leads with the portable detection idiom** — the same pattern used by all 7 workspace command templates + SKILL.md:
   ```bash
   PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
   [ -z "$PY" ] && { echo "Error: Python 3 is required but neither python3 nor python was found"; exit 1; }
   ```
2. **Bakes the resolved interpreter into the generated command field** for both tool variants:
   - Claude Code: `"$PY .claude/hooks/continue-loop.py"`
   - Cursor: `"$PY .cursor/hooks/continue-loop.py"`
3. **Explicitly instructs writing the resolved absolute path into the JSON** — "Write the actual path into the JSON; do not leave the literal `$PY` in the file."

Hook script's `#!/usr/bin/env python3` shebang is preserved for direct-invocation ergonomics but is never resolved at hook-execution time — which was exactly the Windows failure mode (`env: python3: No such file or directory` → exit 127 → Claude Code treats the failed hook as did-not-block → invoke loop dies).

### New regression test
[test_hook_python_detection.py](skills/development-harness/scripts/tests/test_hook_python_detection.py) — 5 cases in `TestCreateDocHookPythonDetection`:
1. Detection idiom present in the Hook configuration subsection (section-sliced so unrelated snippets elsewhere in the doc can't satisfy the assertion).
2. Exact `$PY .claude/hooks/continue-loop.py` command-field string pinned.
3. Exact `$PY .cursor/hooks/continue-loop.py` command-field string pinned.
4. **Forbidden-substring check** against the pre-fix bare-path template (`"command": ".claude/hooks/continue-loop.py"` and Cursor equivalent) — this is the one that catches a regression.
5. The "do not leave the literal $PY" guidance assertion so readers don't misinterpret the JSON snippets as copy-paste templates with an unresolved placeholder.

### Issue state
- [ISSUE_001.json](.harness/issues/ISSUE_001.json): `status: "resolved"`, `resolved: 2026-04-20T09:30:00Z`.
- [state.json](.harness/state.json) issues counter: `total: 2, open: 1, resolved: 1`.

### Grounding
ISSUE_001's suggested `regression_coverage` was "a unit test around a helper that produces the settings-hook JSON given a detected PY." But `create.md` is prose instructions the bootstrapping agent interprets — there's no extractable helper. The doc-shape contract (required + forbidden substrings, section-sliced) is the cleanest regression guard available given the architecture.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_bugfix_002 (PHASE_011):** ISSUE_002 fix — retire the Stop-hook-as-continuation-driver for Claude Code (Cursor hook stays unchanged). Four sub-steps:

1. **Add** [references/claude-code-continuation.md](skills/development-harness/references/claude-code-continuation.md) explaining why Cursor's `followup_message` protocol cannot port to Claude Code's one-shot `stop_hook_active` guard.
2. **Rewrite** [templates/claude-code/hooks/continue-loop.py](skills/development-harness/templates/claude-code/hooks/continue-loop.py) to a **precondition-only** shape: run the authority chain (flag, budget, blockers, open_questions, selector-vs-checkpoint agreement), print an advisory to stdout, **always exit 0**; do not attempt exit-2 block-continue.
3. **Add "Claude Code: run under `/loop`" sections** to [commands/invoke.md](skills/development-harness/commands/invoke.md) and [templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md) pointing Claude Code users at `/loop /invoke-development-harness` as the autonomous-run primitive.
4. **Update** [commands/create.md](skills/development-harness/commands/create.md) Phase 5 so Claude Code installs wire the hook as precondition-checker (not continue-driver).

Large unit — may be split across multiple commits within this unit.

## Blocked By
None.

## Evidence
- [skills/development-harness/commands/create.md](skills/development-harness/commands/create.md): Phase 5 Hook configuration subsection rewrite.
- [skills/development-harness/scripts/tests/test_hook_python_detection.py](skills/development-harness/scripts/tests/test_hook_python_detection.py): new 120-line test module, 5 cases.
- [.harness/issues/ISSUE_001.json](.harness/issues/ISSUE_001.json): status flipped to resolved.
- `python -m py_compile` → 0 (~0.1s) on new test file.
- `python -m unittest skills.development-harness.scripts.tests.test_hook_python_detection -v` → **5/5** in 0.002s.
- `python -m unittest discover skills/development-harness/scripts/tests` → **227/228** + 1 OS skip in 37.3s (up from 223).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, **resolved 2026-04-20**): Windows Python-detection in create.md Phase 5. Fixed by this unit.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot. Next: `unit_bugfix_002`.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_011 PR opens after the last unit closes (still working out how many beyond the two bugfix units the phase contains — see phase-graph.json).
- **Branch:** `feat/phase-011-documentation`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 43 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_011 progress: **1/? units done** — starting the documentation phase with the two ISSUE bugfixes at the head.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → 206 → 210 → 215 → 222 → 223 → **228** across phases so far.

## Batch (current or last)

Reflects `state.execution.fleet`.

- **Batch ID:** none
- **Mode:** idle

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|

### Conflicts
No conflicts.

---
*Updated: 2026-04-20T09:30:00Z*
