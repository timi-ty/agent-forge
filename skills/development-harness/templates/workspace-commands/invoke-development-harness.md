---
description: "Execute the next unit of work from the development harness"
---

# Invoke Development Harness

Read `.harness/ARCHITECTURE.md` for project context.

## 1. Validate

```bash
python3 .harness/scripts/validate_harness.py
```

If invalid, report errors and stop.

## 2. Load State

Read these files:
- `.harness/state.json` — execution pointers, loop budget, checkpoint
- `.harness/checkpoint.md` — human-readable progress summary
- `.harness/phase-graph.json` — canonical phase/unit status

## 3. Select Next Unit

```bash
python3 .harness/scripts/select_next_unit.py
```

- If `found: false` and `all_complete: true` → report completion, stop
- If `found: false` and `all_complete: false` → report blocked, stop
- If `phase_complete: true` → run phase completion review (step 10) before proceeding
- If `found: true` → continue with the selected unit

## 4. Read Phase Context

Read `.harness/PHASES/PHASE_XXX_<slug>.md` for the selected unit's phase. Note the unit's acceptance criteria and validation method from the Units of Work table.

## 5. Plan Internally

Determine files to create/modify, tests to write, and validation to run. Do not switch to Plan Mode. Do not ask the user unless requirements are genuinely ambiguous.

## 6. Implement

Write production code and tests. Match existing codebase patterns.

## 7. Validate

Run applicable validation layers:

1. **Static checks** — linter, type checker (e.g., `pnpm lint`, `tsc --noEmit`)
2. **Unit tests** — relevant test files (e.g., `pnpm test -- tests/foo.test.ts`)
3. **Integration tests** — if integration points were touched
4. **E2E tests** — if configured and user-facing flows were affected

On failure:
- Attempt fix (up to 2 retries per failure type)
- If still failing: add to `checkpoint.blockers`, update `checkpoint.md`, stop
- Do NOT continue to the next unit on failure

On success:
- Record concrete evidence (e.g., `"tests/auth.test.ts passes (5/5)"`)

## 8. Update State

Update all three files:

**phase-graph.json:**
- Unit `status` → `"completed"`, append `validation_evidence`

**state.json:**
- Advance `active_unit`, `last_completed_unit`, `next_unit`
- Increment `session_count`, update `checkpoint` section
- `checkpoint.next_action` MUST match what `select_next_unit.py` returns

**checkpoint.md:**
- What completed, evidence, what's next, any blockers

## 9. Commit

Check for `commit-agent-changes` skill:
```bash
ls ~/.cursor/skills/commit-agent-changes/SKILL.md 2>/dev/null || ls .cursor/skills/commit-agent-changes/SKILL.md 2>/dev/null
```

If found, delegate to the skill. Otherwise, commit directly following `.harness/config.json` git policy:
- Stage changed files
- Write conventional commit message
- Push if on a feature branch with a remote

## 10. Phase Completion Review

When all units in a phase are done:

1. Read `.harness/pr-review-checklist.md` — verify each item
2. If phase is deploy-affecting, check deployment verifier in `config.json`
   - If verifier configured → run it
   - If verifier not configured → add blocker, stop
   - If verifier fails → add blocker, stop
3. Mark phase `"completed"` in `phase-graph.json` only after review passes

## 11. Turn Ends

The stop hook (`continue-loop.py`) fires automatically. It checks loop budget, blockers, open questions, and runs `select_next_unit.py` to determine whether to continue. Do not manually loop.
