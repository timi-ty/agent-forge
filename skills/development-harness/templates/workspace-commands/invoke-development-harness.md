---
description: "Execute the next unit of work from the development harness"
---

# Invoke Development Harness

Read `.harness/ARCHITECTURE.md` for project context.

## 0. Resolve tool paths

Read `.harness/config.json` and check the `tool` field. Set variables:

| Variable | cursor | claude-code |
|----------|--------|-------------|
| `$GLOBAL_SKILLS_DIR` | `~/.cursor/skills` | `~/.claude/commands` |
| `$WORKSPACE_SKILLS_DIR` | `.cursor/skills` | `.claude/commands` |

## 1. Activate Invoke Session

Create the invoke session flag so the stop hook knows this is a harness session:

```bash
touch .harness/.invoke-active
```

This flag is checked by `continue-loop.py`. Without it, the hook is a no-op.

## 2. Detect Python

```bash
PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
[ -z "$PY" ] && { echo "Error: Python 3 is required but neither python3 nor python was found"; exit 1; }
```

## 3. Validate

```bash
$PY .harness/scripts/validate_harness.py
```

If invalid, report errors and stop.

## 4. Load State

Read these files:
- `.harness/state.json` — execution pointers, loop budget, checkpoint
- `.harness/checkpoint.md` — human-readable progress summary
- `.harness/phase-graph.json` — canonical phase/unit status

## 5. Select Next Unit

```bash
$PY .harness/scripts/select_next_unit.py
```

- If `found: false` and `all_complete: true` → report completion, stop
- If `found: false` and `all_complete: false` → report blocked, stop
- If `phase_complete: true` → run phase completion review (step 13) before proceeding
- If `found: true` → continue with the selected unit

## 6. Read Phase Context

Read `PHASES/PHASE_XXX_<slug>.md` for the selected unit's phase. Note the unit's acceptance criteria and validation method from the Units of Work table.

## 7. Exploration (conditional)

If the selected unit's description implies modifying an **existing** system, dispatch an `Explore` sub-agent **before** planning so its output feeds the plan without filling the main context with file reads.

Trigger keywords (run exploration first): `refactor`, `extend`, `fix`, `migrate`, `update`.

Skip keywords (from-scratch units; reading 1–2 sibling files during planning is sufficient): `add`, `new`, `create`, `insert`, `scaffold`.

Dispatch in the same message you plan from. Thoroughness defaults to `medium`; bump to `very thorough` only for cross-cutting concerns (auth, config loading, hook integration, schema migration):

```
Agent(
  description: "<5-word task summary>",
  subagent_type: "Explore",
  prompt: """
    Explore the <area> touched by unit <unit_id>.

    Unit goal: <one-line paraphrase of unit_description>.

    Report: (1) every file that currently implements the behavior,
    (2) any nearby tests that will need to change,
    (3) conventions the new code must match (naming, error handling, test harness),
    (4) risks or prior-art gotchas that the plan needs to account for.
    Under 400 words.
  """
)
```

Absorb the report into section 8's plan — specifically the files-to-modify list and dependencies. Do not re-read files the Explore agent already reported on. Exploration is a tool for the main agent, not a delegation of the implementation; the main agent still does the editing, testing, and commit.

## 8. Plan Internally

Determine files to create/modify, tests to write, and validation to run. Do not switch to Plan Mode. Do not ask the user unless requirements are genuinely ambiguous.

## 9. Implement

Write production code and tests. Match existing codebase patterns.

**Multi-file parallel edits.** When the plan from section 8 touches **≥4 independent files** whose edits do not depend on each other, fan the work out in a **single assistant message** with **2–3 `Agent(subagent_type: "general-purpose")` tool calls**. More than 3 concurrent agents creates coordination overhead; fewer than 2 means you should edit in the main context. Group by independence, not file count — any edit that reads the output of another (e.g., a rename with cascading callsite updates) belongs in one place. Below the ≥4 threshold, prefer direct `Edit` / `Write` calls in the main context.

## 10. Validate

Run applicable validation layers:

1. **Static checks** — linter, type checker (e.g., `pnpm lint`, `tsc --noEmit`)
2. **Unit tests** — relevant test files (e.g., `pnpm test -- tests/foo.test.ts`)
3. **Integration tests** — if integration points were touched
4. **E2E tests** — if configured and user-facing flows were affected

**Parallel Layer 1 + Layer 2 (when enabled).** When `config.agent_delegation.parallel_validation_layers == true`, fan Layer 1 (lint + typecheck + formatter) and Layer 2 (unit tests) out as concurrent `Bash` tool calls in a **single assistant message** (lint, typecheck, and unit-test calls share no state). The unit passes only if every parallel call exits 0; any failure falls into the On Failure flow below and **no** Layer 3 or Layer 4 advancement. **Layers 3 and 4 stay serial** — integration + E2E commonly contend on ports, fixtures, databases, and test accounts. When the flag is `false` (default), run the four layers sequentially as listed above — flag-off behavior is unchanged from v1.

On failure:
- Attempt fix (up to 2 retries per failure type)
- If still failing: add to `checkpoint.blockers`, update `checkpoint.md`, stop
- Do NOT continue to the next unit on failure

On success:
- Record concrete evidence **with per-layer wall-clock timing** (e.g., `"pnpm lint exits 0 (2.1s)"`, `"tsc --noEmit exits 0 (4.8s)"`, `"tests/auth.test.ts passes (5/5, 3.2s)"`). The timing makes the parallel-layers benefit visible in checkpoint history — when Layer 1 + Layer 2 ran in a single assistant message, a reader can see the unit's validation wall-clock was `max(layer_1, layer_2)` rather than the sum.

## 11. Update State

Update all three files:

**phase-graph.json:**
- Unit `status` → `"completed"`, append `validation_evidence`

**state.json:**
- Advance `active_unit`, `last_completed_unit`, `next_unit`
- Increment `session_count`, update `checkpoint` section
- `checkpoint.next_action` MUST match what `select_next_unit.py` returns

**checkpoint.md:**
- What completed, evidence, what's next, any blockers

## 12. Commit

Check for `commit-agent-changes` skill:
```bash
ls $GLOBAL_SKILLS_DIR/commit-agent-changes/SKILL.md 2>/dev/null || ls $WORKSPACE_SKILLS_DIR/commit-agent-changes/SKILL.md 2>/dev/null
```

If found, delegate to the skill. Otherwise, commit directly following `.harness/config.json` git policy:
- Stage changed files
- Write conventional commit message
- Push if on a feature branch with a remote

At **phase completion**, this may already have been dispatched in parallel with `code-review` per section 13's parallel-dispatch paragraph; in that case skip the separate delegation above.

## 13. Phase Completion Review

When all units in a phase are done:

1. Read `.harness/pr-review-checklist.md` — verify each item
2. If phase is deploy-affecting, check deployment verifier in `config.json`
   - If verifier configured → run it
   - If verifier not configured → add blocker, stop
   - If verifier fails → add blocker, stop
3. Mark phase `"completed"` in `phase-graph.json` only after review passes

**Parallel dispatch.** When **both** `code-review` and `commit-agent-changes` are installed, dispatch them concurrently at phase completion in a **single assistant message** containing **two `Agent(subagent_type: "general-purpose")` tool calls** — one running `code-review` read-only on the current branch diff, the other running `commit-agent-changes` to commit pending changes, push, and open or update the phase PR. They cannot conflict (one reads, one writes disjoint state). Wait for both reports, then resolve any High/Medium code-review findings in the main context and re-push. If only one skill is installed, fall back to serial — no parallel dispatch.

## 14. Turn Ends

The stop hook (`continue-loop.py`) fires automatically. It checks for the `.harness/.invoke-active` flag first -- if absent, the hook is a no-op. If present, it checks loop budget, blockers, open questions, and runs `select_next_unit.py` to determine whether to continue. When the hook decides to stop, it deletes the flag. Do not manually loop.
