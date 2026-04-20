# Command: Invoke

Execute the next **batch** of work from the harness. **One turn = one batch.** A batch is always a list of units; whether the list has size 1 or size N, every step applies uniformly. Only Steps 5 and 6 branch between an in-tree fast path (size 1, parallelism off) and a worktree fan-out (everything else). Every other step is single-flow.

**Mode:** Execution mode. Do NOT switch to Plan Mode.

### Claude Code: run under `/loop`

On Claude Code, `/invoke-development-harness` runs **exactly one batch per turn by protocol** — Claude Code's Stop hook has a one-shot `stop_hook_active` guard that a force-continue driver cannot beat. For autonomous multi-turn runs, invoke this command under the native `/loop` skill:

```
/loop /invoke-development-harness
```

`/loop` fires the command now and re-fires on its schedule; each firing is a fresh session, so `stop_hook_active` never accumulates. The harness's own `loop_budget` (in `state.json`) remains the cap. The Stop hook runs in **precondition-checker mode** on Claude Code — it prints an advisory describing whether to proceed or stop, then always exits 0. See [references/claude-code-continuation.md](../references/claude-code-continuation.md) for the full protocol explanation (ISSUE_002).

Cursor is unchanged: its Stop hook still drives continuation via `followup_message`. Direct `/invoke-development-harness` on Cursor auto-continues the harness's own `loop_budget` worth of turns.

---

## Step 0: Detect Host Tool

Determine whether you are running in **Cursor** or **Claude Code**.

Set the following variables:

| Variable | Cursor | Claude Code |
|----------|--------|-------------|
| `$TOOL` | `cursor` | `claude-code` |
| `$TOOL_DIR` | `.cursor` | `.claude` |
| `$GLOBAL_SKILLS_DIR` | `~/.cursor/skills` | `~/.claude/commands` |
| `$WORKSPACE_SKILLS_DIR` | `.cursor/skills` | `.claude/commands` |

---

## Step 1: Activate Invoke Session

```bash
touch .harness/.invoke-active
```

Without this flag the Claude Code stop hook is a no-op, so a non-harness agent session in the same workspace is unaffected.

---

## Step 2: Validate Harness

```bash
$PY .harness/scripts/validate_harness.py
```

If validation fails, report the errors and **stop**. Do not proceed with invalid harness state.

---

## Step 3: Load State

Read the three state files:

1. **`.harness/state.json`** — current phase, unit pointers, loop budget, checkpoint, blockers, `execution.fleet` (mode + units).
2. **`.harness/checkpoint.md`** — human-readable summary.
3. **`.harness/phase-graph.json`** — canonical phase/unit status and dependencies.

Parse `state.json`; note `execution.fleet.mode`. If it is **not** `"idle"` (`"dispatched"` or `"merging"`), a previous turn did not finish cleanly — stop and report. Recovery lives in `/sync` + `teardown_batch.py`.

---

## Step 4: Compute Batch

Compute the frontier, then pack the largest safe batch:

```bash
$PY .harness/scripts/select_next_unit.py --frontier > .harness/logs/frontier.json
$PY .harness/scripts/compute_parallel_batch.py \
    --input .harness/logs/frontier.json \
    --config .harness/config.json \
    > .harness/logs/batch.json
```

Read `batch.json`: `{batch_id, batch, excluded}`.

- **`batch == []` and `all_complete: true`** (from a follow-up `select_next_unit.py` no-flag call) → every phase is complete. Report and **stop**.
- **`batch == []` and `all_complete: false`** → everything on the frontier was excluded (scope/capacity/not-parallel-safe) or the frontier was empty due to blocking dependencies. Report with the `excluded` reasons and **stop**.
- **`batch` non-empty** → proceed with that list.

### Pick the dispatch mode

- **In-tree fast path** — `len(batch) == 1` AND `config.execution_mode.parallelism.enabled == false`.
- **Worktree fan-out** — every other case, including `len(batch) == 1` when parallelism is on (used by the batch-of-1 regression test in PHASE_009 to verify the fan-out path and the in-tree path produce identical final state).

This decision only affects **Steps 5 and 6**. From Step 7 onward, the two paths converge.

---

## Step 5: Dispatch

### In-tree fast path

No worktree creation. The current working tree is the "worktree" for this single unit. Record a fleet entry in memory (not yet persisted):

```json
{
  "batch_id": "<batch_id>",
  "unit_id": "<unit_id>",
  "phase_id": "<phase_id>",
  "worktree_path": null,
  "branch": "<current-branch-or-null>",
  "status": "running",
  "started_at": "<iso-ts>",
  "ended_at": null,
  "agent_summary_path": null,
  "conflict": null
}
```

Leave `state.execution.fleet.mode` as `"idle"` — the in-tree path never enters a dispatched-batch state.

### Worktree fan-out

```bash
$PY .harness/scripts/dispatch_batch.py \
    --batch .harness/logs/batch.json \
    --state .harness/state.json
```

This creates per-unit worktrees under `.harness/worktrees/<batch_id>/<unit_id>`, creates `harness/<batch_id>/<unit_id>` branches, seeds `<worktree>/.harness/WORKTREE_UNIT.json`, and flips `state.execution.fleet.mode` to `"dispatched"` with one `status: "running"` entry per unit. Atomic on failure.

---

## Step 6: Execute

### In-tree fast path

Execute the single unit inline, following its row in `PHASES/PHASE_XXX_<slug>.md`'s Units-of-Work table (description, acceptance criteria, validation method).

**Optional Exploration (main agent).** If the unit description contains `refactor`, `extend`, `fix`, `migrate`, or `update`, dispatch an `Agent(subagent_type: "Explore", thoroughness: "medium")` **before** planning, so its output feeds the plan without filling the main context with file reads. Skip for from-scratch work (`add`, `new`, `create`, `insert`, `scaffold`).

**Multi-file parallel edits.** If the plan touches **≥4 independent files** with no read-after-write ordering, fan the work out in a **single assistant message** with **2–3 `Agent(subagent_type: "general-purpose")` tool calls**. Below 4 files, edit inline with `Edit` / `Write`. See `templates/claude-code/rules/harness-core.md` Delegation section for the full rule.

Record validation evidence with per-layer wall-clock timing (e.g., `"pnpm lint exits 0 (2.1s)"`). When `config.execution_mode.agent_delegation.parallel_validation_layers == true`, fan Layer 1 (lint + typecheck) and Layer 2 (unit tests) out as concurrent `Bash` tool calls in a single assistant message. Layers 3 and 4 stay serial.

### Worktree fan-out

Dispatch one `Agent(subagent_type: "harness-unit")` call **per unit** in a **single assistant message**. The agent definition in [templates/claude-code/agents/harness-unit.md](../templates/claude-code/agents/harness-unit.md) carries the full contract (tool allowlist, workflow, required JSON report schema); the briefing only needs to hand over the identity.

```
# One assistant message, N parallel tool calls:
Agent(
  description: "<unit_id> (<phase_id>)",
  subagent_type: "harness-unit",
  prompt: """
    Your worktree: <absolute path>.
    Your unit: <unit_id> in <phase_id>.
    Declared touches_paths: <globs>.

    Read .harness/WORKTREE_UNIT.json for the full identity.
    Read PHASES/PHASE_XXX_<slug>.md for the Unit-of-Work row
    (description + acceptance criteria + validation method).

    Follow the harness-unit contract (templates/claude-code/agents/harness-unit.md):
    worktree-only writes, no push/merge/rebase, commit on the
    pre-created harness/<batch_id>/<unit_id> branch, emit the
    required JSON report at the end of your turn.
  """
)
```

Wait for every sub-agent to return. Parse each JSON report (`unit_id`, `status`, `validation_evidence`, `commits`, `touched_paths_actual`, `failure`). Update the in-memory fleet entry for each unit with `ended_at` and the reported status.

The scope-violation check that actually **gates the merge** runs inside `merge_batch.py` (Step 8), not here — the sub-agent's self-report is never trusted for blast radius.

---

## Step 7: Verify (scope + report hygiene)

For both paths, verify that every unit's report / diff is internally consistent **before** attempting the merge:

- **In-tree fast path.** Run `git diff --name-only` on the working tree (vs. `HEAD`). Any file that does not match the unit's declared `touches_paths` → force the unit's status to `"failed"` with `conflict = {paths: <violators>, category: "scope_violation"}` and skip to Step 9. Do not commit the out-of-scope changes.
- **Worktree fan-out.** The in-band scope check runs inside `merge_batch.py` per PHASE_005 unit_022; you don't re-run it here. But **do reject any sub-agent report whose `failure` is populated** — those units will be marked `"failed"` at Step 9 with the category the sub-agent reported.

Report-hygiene checks (both paths):

- `unit_id` in every report matches the dispatched unit.
- `status` ∈ `{"succeeded", "failed"}`.
- `failure` is `null` iff `status == "succeeded"`.
- `commits` is non-empty when `status == "succeeded"`.

Hygiene violations are infrastructure failures — mark the unit `"failed"` with `category: "infrastructure"` and continue.

---

## Step 8: Merge

### In-tree fast path

**No-op.** The unit's changes are already on the current branch (no worktree, no separate branch, no fan-in). `state.execution.fleet.mode` stays `"idle"` throughout.

### Worktree fan-out

```bash
$PY .harness/scripts/merge_batch.py \
    --state .harness/state.json \
    --conflict-strategy abort_batch
```

`merge_batch.py` owns the whole serial fan-in:

1. Acquires the `.harness/.lock` `O_EXCL` mutex (blocks if another invoker is merging).
2. Flips `state.execution.fleet.mode` to `"merging"`.
3. For each unit: runs the scope-violation check (diff vs. declared `touches_paths`); on violation, fails the unit and skips its merge. On clean scope, runs `git merge --no-ff harness/<batch_id>/<unit_id> -m "harness: merge <unit_id>"`.
4. Applies the configured `conflict_strategy` on merge conflicts.
5. Runs post-merge validation (default: no-op; wire a real validator when needed).
6. On validation failure: `git reset --hard <pre-merge-ref>` and downgrades merged units to `failed` with `category: "post_merge_validation_failed"`.
7. On success: `git worktree remove --force` + `git branch -D` per merged unit; prunes the empty `.harness/worktrees/<batch_id>/` dir.
8. Flips `state.execution.fleet.mode` back to `"idle"`.

The returned JSON (`outcome`, `merged`, `conflicted`, `skipped`, `validation_evidence`) drives the Step 9 state updates.

---

## Step 9: State Update & Phase Completion

### 9a: Update phase-graph.json

For every unit that `"succeeded"` (in-tree) or `"merged"` (worktree fan-out):
- `status` → `"completed"`.
- Append validation evidence entries with per-layer timings.

For every unit that `"failed"` or had a scope violation:
- Leave `status` as `"pending"` — the unit gets re-decomposed or re-run on a later turn (PHASE_009's safety rails automate the re-decompose decision). **Do not mark it `"failed"`** at the unit level; the failure lives in `state.json.checkpoint.blockers` instead.

### 9b: Update state.json

- `execution.last_completed_unit` → most recently completed unit in list order (or unchanged if no unit completed this turn).
- `execution.active_unit` → null.
- `execution.next_unit` → the `unit_id` that `select_next_unit.py` (no-flag) returns now.
- `execution.session_count` → **increment by 1** (one turn, regardless of batch size).
- `checkpoint.summary` — what this turn's batch accomplished.
- `checkpoint.blockers` — any failed units with their failure categories.
- `checkpoint.next_action` — **MUST include the `unit_id`** that `select_next_unit.py` returns, so the Claude Code stop hook's agreement check passes.
- `checkpoint.timestamp`, `last_updated` — current ISO timestamp.

### 9c: Phase Completion Review (when applicable)

If this turn marked the last unit of a phase `"completed"`:
- Read `.harness/pr-review-checklist.md` and verify each item.
- If the phase is deploy-affecting (per its PHASE doc), run the deployment verifier from `config.json`. If the verifier is missing or fails, add a blocker and stop — do **not** mark the phase complete.
- If the phase is not deploy-affecting, skip the deployment gate.
- Only after the checklist + deployment gate pass: set the phase `"completed"` in phase-graph.json.

### 9d: Update checkpoint.md

Refresh:
- **Last Completed** — every unit this turn completed, with evidence.
- **What Failed** — any per-unit failures with categories (or "None").
- **What Is Next** — `select_next_unit.py`'s next action.
- **Blocked By** — blockers (or "None").
- **Evidence** — summary of validation evidence.
- **Open Questions** — (or "None").

---

## Step 10: Commit

### Check for installed skills

```bash
ls $GLOBAL_SKILLS_DIR/commit-agent-changes/SKILL.md 2>/dev/null || ls $WORKSPACE_SKILLS_DIR/commit-agent-changes/SKILL.md 2>/dev/null
ls $GLOBAL_SKILLS_DIR/code-review/SKILL.md 2>/dev/null || ls $WORKSPACE_SKILLS_DIR/code-review/SKILL.md 2>/dev/null
```

### Parallel dispatch (at phase completion, when both skills are installed)

When **this turn closed a phase** (9c ran and marked the phase `"completed"`) AND **both** `code-review` and `commit-agent-changes` are installed, dispatch them **in one assistant message** with two `Agent(subagent_type: "general-purpose")` tool calls:

```
# One assistant message:
Agent(
  description: "phase review PHASE_XXX",
  subagent_type: "general-purpose",
  prompt: "Run the code-review skill on the current branch (or the open PR for this branch) covering every commit since the branch diverged from <base>. Report High/Medium/Low findings. Read-only."
)
Agent(
  description: "commit + PR for PHASE_XXX",
  subagent_type: "general-purpose",
  prompt: "Run the commit-agent-changes skill: group the pending phase changes into logical commits on the current feature branch, push, and open or update the phase PR with the conventional title and body."
)
```

Wait for both; resolve any High/Medium code-review findings in the main context and re-push. Disjoint state (one reads, one writes non-overlapping files) — they cannot conflict.

### Fallback: serial

- When no phase closed this turn, **or** only one of the two skills is installed, delegate commit/PR creation to `commit-agent-changes` alone (or commit directly via `git` + conventional-commits message + push if neither skill is installed).
- In the fallback path, `code-review` — if installed — runs after the PR exists, not in parallel with its creation.

---

## Step 11: Turn Ends

The agent's turn ends here. The stop hook (`continue-loop.py`) fires automatically:

1. Checks `.harness/.invoke-active` — absent ⇒ hook is a no-op (protects non-harness sessions in the same workspace).
2. Respects Claude Code's built-in `stop_hook_active` loop guard.
3. Reads `state.json` for loop budget, blockers, open questions.
4. Runs `select_next_unit.py` for the authoritative next unit.
5. Compares selector output against `checkpoint.next_action`.
6. If they **agree** and all conditions pass → continue the loop (Cursor: `followup_message`; Claude Code: exit 2 + `decision: block`).
7. If they **disagree** or any gate fails → stop (Cursor: `{}`; Claude Code: exit 0 + delete `.invoke-active`).

**Claude Code note (see [ISSUE_002](../../.harness/issues/ISSUE_002.json)).** Claude Code's Stop hook has a one-shot `stop_hook_active` guard that caps hook-driven continuations at 1. For multi-turn autonomous runs, use **`/loop /invoke-development-harness`** instead of relying on the stop hook to chain turns. The stop hook's authority-chain checks (budget / blockers / selector agreement) are still valuable as a per-turn precondition gate; they just don't drive N-turn continuation on Claude Code. Cursor's hook works as originally designed.

Do NOT manually loop or call invoke again from within this turn. The hook (or `/loop`) handles continuation.

---

## Stop Conditions

Update `checkpoint.md` and `state.json` to signal a stop when any of these occur:

| Condition | Action |
|-----------|--------|
| All phases complete | Report full completion; stop. |
| Batch is empty (frontier blocked) | Report `excluded` reasons; stop. |
| `state.execution.fleet.mode != "idle"` at start of turn | Previous turn left state dispatched/merging — stop and run `/sync`. |
| Ambiguous requirements encountered | Add to `open_questions`; stop. |
| Repeated validation failures (after 2 retries in-tree, or sub-agent failures in fan-out) | Add to `blockers`; stop. |
| Missing credentials or infrastructure | Add to `blockers`; stop. |
| Product judgment required | Add to `open_questions`; stop. |
| Loop budget approaching limit | Update checkpoint summary; let hook / `/loop` enforce. |

---

## Skills Integration

At the start of execution, check for installed skills (output-only; only invoke them at the appropriate steps above):

```bash
ls $GLOBAL_SKILLS_DIR/commit-agent-changes/SKILL.md 2>/dev/null || ls $WORKSPACE_SKILLS_DIR/commit-agent-changes/SKILL.md 2>/dev/null
ls $GLOBAL_SKILLS_DIR/code-review/SKILL.md 2>/dev/null || ls $WORKSPACE_SKILLS_DIR/code-review/SKILL.md 2>/dev/null
```

- **commit-agent-changes** — used at Step 10 (commit/PR workflow).
- **code-review** — used at Step 10 in parallel with commit-agent-changes when a phase closes this turn.
