# Command: Invoke

Execute the next unit of work from the harness. This is the primary runtime command.

**Mode:** Execution mode. Do NOT switch to Plan Mode. The stop hook (`continue-loop.py`) handles loop continuation via hook-driven bounded continuation.

---

## Step 1: Activate Invoke Session

Create the invoke session flag so the stop hook knows this is a harness session:

```bash
touch .harness/.invoke-active
```

This flag is checked by `continue-loop.py`. Without it, the hook is a no-op and will not interfere with non-harness agent sessions.

---

## Step 2: Validate Harness

Run the harness validator:

```bash
python3 .harness/scripts/validate_harness.py
```

If validation fails, report the errors to the user and **stop**. Do not proceed with invalid harness state.

---

## Step 3: Load State

Read the three state files to establish execution context:

1. **`.harness/state.json`** — current phase, unit pointers, loop budget, checkpoint, blockers
2. **`.harness/checkpoint.md`** — human-readable summary of progress, blockers, and next action
3. **`.harness/phase-graph.json`** — canonical source of truth for phase/unit status and dependencies

Parse `state.json` into memory. Note `execution.active_phase`, `execution.active_unit`, `execution.loop_budget`, `checkpoint.blockers`, and `checkpoint.open_questions`.

---

## Step 4: Select Next Unit

Run the authoritative unit selector:

```bash
python3 .harness/scripts/select_next_unit.py
```

Interpret the JSON output:

- **`found: false` and `all_complete: true`** — All phases are complete. Report completion to the user and **stop**.
- **`found: false` and `all_complete: false`** — No executable unit (likely blocked by dependencies). Report the situation and **stop**.
- **`phase_complete: true`** — A previous phase has all units completed but is not yet marked complete. Run the **phase completion review** (Step 9) for that phase before proceeding to the selected unit.
- **`found: true`** — Proceed with the selected `phase_id`, `unit_id`, and `unit_description`.

---

## Step 5: Read Phase Context

Read the relevant phase document:

```
PHASES/PHASE_XXX_<slug>.md
```

Where `XXX` and `<slug>` come from the phase containing the selected unit. Understand:

- The unit's **acceptance criteria** (from the Units of Work table)
- The unit's **validation method** (from the Units of Work table)
- The phase's **validation gates** and **deployment implications**
- The phase's **scope** and **non-goals** (to avoid scope creep)

---

## Step 6: Plan the Unit

Internally determine (do NOT switch to Plan Mode):

1. **Files to create or modify** — identify each file and the nature of the change
2. **Tests to write** — unit tests are mandatory for testable code; integration/E2E if applicable
3. **Validation to run** — which layers of the validation hierarchy apply (see Step 8)
4. **Dependencies** — any packages to install, configs to update, migrations to run

Do not ask the user unless requirements are genuinely ambiguous. If the phase document and codebase provide enough information, proceed autonomously.

---

## Step 7: Implement the Unit

Write the code:

1. Check existing codebase patterns first — match naming, structure, style, and idioms
2. Write production code that satisfies the unit's acceptance criteria
3. Write or update tests that prove the acceptance criteria are met
4. If the unit involves new APIs or interfaces, ensure they align with the phase document's scope

---

## Step 8: Validate

Run applicable layers of the validation hierarchy. Only run layers that are relevant to the changes made:

### Layer 1: Static Checks
Run linter, type checker, and formatter as configured in the project:
```bash
# Examples (adapt to project's actual tooling):
pnpm lint          # or: npm run lint, ruff check, etc.
pnpm typecheck     # or: tsc --noEmit, mypy, etc.
```

### Layer 2: Unit Tests
Run the test files relevant to the unit's changes:
```bash
# Examples:
pnpm test -- tests/auth.test.ts    # run specific test file
pytest tests/test_auth.py           # or Python equivalent
```

### Layer 3: Integration Tests
If the unit touches integration points (API boundaries, database interactions, service communication), run integration tests:
```bash
pnpm test:integration    # or project-specific command
```

### Layer 4: E2E Tests
If configured in `config.json` (`testing.e2e_framework`) and the unit affects user-facing flows:
```bash
pnpm test:e2e    # or: npx playwright test, etc.
```

### On Failure

If any validation layer fails:

1. **Attempt a fix** — analyze the error, fix the code
2. **Re-run the failed validation** — confirm the fix works
3. **Retry limit: 2 attempts per failure type** — if the same category of failure persists after 2 fix attempts:
   - Update `checkpoint.md` with failure details (what failed, what was tried)
   - Add the failure to `state.json` `checkpoint.blockers`
   - Do NOT advance to the next unit
   - **Stop**

### On Success

Record specific evidence for each passing layer. Evidence must be concrete:

- **Good:** `"tests/auth.test.ts passes (5/5 assertions)"`, `"tsc --noEmit exits 0"`, `"pnpm lint exits 0"`
- **Bad:** `"tests pass"`, `"looks good"`, `"validated"`

---

## Step 9: Phase Completion Review

This step runs when all units in a phase are completed (signaled by `phase_complete: true` from select_next_unit.py, or when the unit just completed was the last pending unit in its phase).

### 9a: Run Review Checklist

Read `.harness/pr-review-checklist.md` (workspace copy) or fall back to `templates/rules/pr-review-checklist.md` from this skill. Verify each item:

- [ ] All units have validation evidence in phase-graph.json
- [ ] No linter errors in changed files
- [ ] No type errors in changed files
- [ ] Code follows existing codebase patterns
- [ ] Unit tests pass for all new/modified code
- [ ] Integration tests pass (if applicable)
- [ ] E2E tests pass (if applicable and configured)
- [ ] All changes committed following git policy
- [ ] Checkpoint updated with completion summary

### 9b: Deployment Truth Gate

Check the phase document's **Deployment Implications** section.

If the phase is **deploy-affecting**:
1. Check `config.json` for `deployment.verification_method` and `deployment.smoke_test_url`
2. If a deployment verifier is configured, run it (e.g., check smoke test URL, run deployed E2E)
3. If the deployment verifier is **not configured**, add a blocker: `"Deploy-affecting phase <PHASE_ID> requires deployment verifier but none is configured"` and **stop**
4. If the deployment verifier **fails**, add a blocker with failure details and **stop**

If the phase is **not deploy-affecting**, skip this gate.

### 9c: Mark Phase Complete

Only after the review checklist passes and deployment gate (if applicable) passes:
- Set the phase's `status` to `"completed"` in `phase-graph.json`
- Set the phase's `completed` timestamp in `phase-graph.json`

---

## Step 10: Update State

After each completed unit, update all three state files atomically (complete all updates before moving on):

### phase-graph.json
- Set the unit's `status` to `"completed"`
- Append concrete validation evidence to the unit's `validation_evidence` array
- If this was the last unit in the phase and the phase completion review passed, set the phase's `status` to `"completed"` and record `completed` timestamp

### state.json
- `execution.active_unit` → the unit just completed (or next unit if advancing)
- `execution.last_completed_unit` → the unit just completed
- `execution.next_unit` → what comes next (run `select_next_unit.py` if unsure)
- `execution.session_count` → increment by 1
- `checkpoint.summary` → brief description of what was accomplished
- `checkpoint.blockers` → current blockers (empty array if none)
- `checkpoint.open_questions` → current questions (empty array if none)
- `checkpoint.next_action` → description of the next unit to execute
- `checkpoint.timestamp` → current ISO timestamp
- `last_updated` → current ISO timestamp

**CRITICAL:** `state.checkpoint.next_action` must include the unit ID that `select_next_unit.py` would return (e.g., `"Complete unit_003: /api/users CRUD endpoints"`). The stop hook checks that `selected_unit` appears in `checkpoint.next_action` — if the unit ID is missing from the text, the hook stops. If unsure, run `select_next_unit.py` and use its output to populate this field.

### checkpoint.md
Update the human-readable checkpoint:
- **Last Completed** → what unit was completed and its evidence
- **What Failed** → any failures encountered (or "None")
- **What Is Next** → next unit description (must agree with state.json)
- **Blocked By** → current blockers (or "None")
- **Evidence** → summary of validation evidence
- **Open Questions** → any questions (or "None")

---

## Step 11: Commit

### Check for commit-agent-changes skill

Look for the skill:
```bash
ls ~/.cursor/skills/commit-agent-changes/SKILL.md 2>/dev/null || ls .cursor/skills/commit-agent-changes/SKILL.md 2>/dev/null
```

**If found:** Read the skill file and delegate the commit/PR workflow to it. The skill handles branch creation, commit grouping, and PR creation.

**If not found:** Commit directly following `config.json` git policy:

1. Stage changed files (both product code and harness state files):
   ```bash
   git add <changed-files>
   ```
2. Write a conventional commit message based on `config.json` `git.commit_convention`:
   ```bash
   git commit -m "feat(<scope>): <description of unit work>"
   ```
3. Push if on a feature branch with a remote:
   ```bash
   git push
   ```

---

## Step 12: Turn Ends

The agent's turn ends here. The stop hook (`continue-loop.py`) fires automatically after the agent completes. It will:

1. Check for `.harness/.invoke-active` — if absent, the hook is a no-op (this prevents the hook from hijacking non-harness agent sessions)
2. Check if status is "completed" (only continues on completed)
3. Check `execution.loop_budget` — stop if budget exhausted
4. Check `checkpoint.blockers` — stop if any blockers exist
5. Check `checkpoint.open_questions` — stop if any open questions exist
6. Run `select_next_unit.py` for authoritative next unit
7. Compare selector output against `checkpoint.next_action`
8. If they **agree** and all conditions pass → return `followup_message` to continue the loop
9. If they **disagree** → stop (disagreement = ambiguity)

When the hook decides to stop, it deletes `.harness/.invoke-active` to reset the gate for the next session.

Do NOT manually loop or call invoke again. The hook handles continuation.

---

## Stop Conditions

Update `checkpoint.md` and `state.json` to signal a stop when any of these occur:

| Condition | Action |
|-----------|--------|
| All units in current phase complete | Report phase completion; hook will advance or stop |
| All phases complete | Report full completion; stop |
| Ambiguous requirements encountered | Add to `open_questions`; stop |
| Repeated validation failures (after 2 retries) | Add to `blockers`; stop |
| Missing credentials or infrastructure | Add to `blockers`; stop |
| Product judgment required | Add to `open_questions`; stop |
| Loop budget approaching limit | Update checkpoint summary; let hook enforce |

---

## Skills Integration

At the start of execution, check for installed Cursor skills:

```bash
ls ~/.cursor/skills/commit-agent-changes/SKILL.md 2>/dev/null || ls .cursor/skills/commit-agent-changes/SKILL.md 2>/dev/null
ls ~/.cursor/skills/code-review/SKILL.md 2>/dev/null || ls .cursor/skills/code-review/SKILL.md 2>/dev/null
```

- **commit-agent-changes**: If available, use it for Step 11 (commit/PR workflow)
- **code-review**: If available, use it during Step 9 (phase completion review) to get an AI code review of the phase's changes before marking complete

Note their availability but only invoke them at the appropriate steps.
