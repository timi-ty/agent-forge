---
description: "Execute the next batch of work from the development harness"
---

# Invoke Development Harness

Read `.harness/ARCHITECTURE.md` for project context.

**One turn = one batch.** Steps 5 and 6 are the only branch points (in-tree fast path vs worktree fan-out); every other step is single-flow and applies to both batch sizes.

## 0. Resolve tool paths

Read `.harness/config.json` and check the `tool` field. Set variables:

| Variable | cursor | claude-code |
|----------|--------|-------------|
| `$GLOBAL_SKILLS_DIR` | `~/.cursor/skills` | `~/.claude/commands` |
| `$WORKSPACE_SKILLS_DIR` | `.cursor/skills` | `.claude/commands` |

## 1. Activate Invoke Session

```bash
touch .harness/.invoke-active
```

Without this flag the Claude Code stop hook is a no-op (protects non-harness sessions in the same workspace).

## 2. Detect Python

```bash
PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
[ -z "$PY" ] && { echo "Error: Python 3 is required but neither python3 nor python was found"; exit 1; }
```

## 3. Validate

```bash
$PY .harness/scripts/validate_harness.py
```

If invalid, report errors and stop. Also: if `state.execution.fleet.mode` is **not** `"idle"` (`"dispatched"` or `"merging"`), a previous turn did not finish cleanly — stop and run `/sync` + `teardown_batch.py`.

## 4. Compute Batch

```bash
$PY .harness/scripts/select_next_unit.py --frontier > .harness/logs/frontier.json
$PY .harness/scripts/compute_parallel_batch.py \
    --input .harness/logs/frontier.json \
    --config .harness/config.json \
    > .harness/logs/batch.json
```

Read `batch.json` → `{batch_id, batch, excluded}`.

- `batch == []` and `all_complete: true` → all phases complete, stop.
- `batch == []` and `all_complete: false` → frontier blocked, report `excluded` reasons, stop.
- `batch` non-empty → proceed.

**Pick dispatch mode** — **In-tree fast path** when `len(batch) == 1 && config.execution_mode.parallelism.enabled == false`; **Worktree fan-out** otherwise. Only Steps 5 and 6 branch on this; Steps 7–11 converge.

## 5. Dispatch

**In-tree fast path.** Current working tree is the "worktree" for the single unit. No `dispatch_batch.py`; `state.execution.fleet.mode` stays `"idle"`.

**Worktree fan-out.**
```bash
$PY .harness/scripts/dispatch_batch.py --batch .harness/logs/batch.json --state .harness/state.json
```
Creates per-unit worktrees under `.harness/worktrees/<batch_id>/<unit_id>`, `harness/<batch_id>/<unit_id>` branches, seeds `WORKTREE_UNIT.json`; flips `state.execution.fleet.mode` to `"dispatched"`. Atomic on failure.

## 6. Execute

**In-tree fast path.** Execute the single unit inline following its row in `PHASES/PHASE_XXX_<slug>.md`. Optional `Agent(Explore)` before planning when the unit description contains `refactor`/`extend`/`fix`/`migrate`/`update`. Multi-file parallel edits: when the plan touches ≥4 independent files, fan out with 2–3 `Agent(general-purpose)` calls in one assistant message. When `config.execution_mode.agent_delegation.parallel_validation_layers == true`, fan Layer 1 + Layer 2 out as concurrent `Bash` calls in a single assistant message.

**Worktree fan-out.** Dispatch one `Agent(subagent_type: "harness-unit")` call **per unit** in a **single assistant message**. The agent template at `templates/claude-code/agents/harness-unit.md` carries the full contract (tool allowlist, workflow, required JSON report schema); the briefing hands over identity only. Wait for every sub-agent to return; parse the JSON reports.

## 7. Verify

**In-tree:** `git diff --name-only` vs `HEAD`; any file not matching the unit's declared `touches_paths` → force `status: "failed"` with `conflict.category: "scope_violation"` and skip to section 9. The sub-agent self-report is never trusted for blast radius.

**Worktree fan-out:** the scope-violation check runs inside `merge_batch.py` (section 8) — don't re-run here. Also run **report-hygiene checks** on each sub-agent report: `unit_id` matches the dispatched unit, `status` ∈ {succeeded, failed}, `failure` is null iff `succeeded`, `commits` non-empty on success. Hygiene violations → force `failed` with `category: "infrastructure"`.

## 8. Merge

**In-tree:** no-op. Changes are already on the current branch.

**Worktree fan-out:**
```bash
$PY .harness/scripts/merge_batch.py --state .harness/state.json --conflict-strategy abort_batch
```
Acquires `.harness/.lock`, flips `fleet.mode` to `"merging"`, runs scope-violation check + serial `git merge --no-ff` + configured `conflict_strategy` + post-merge validation + `git reset --hard <pre-merge-ref>` rollback on failure + worktree/branch cleanup per merged unit. Mode returns to `"idle"` at the end.

## 9. State Update & Phase Completion

**9a. phase-graph.json.** Units that succeeded this turn → `status: "completed"` with validation evidence appended. Units that failed or had a scope violation stay `"pending"`; the failure lives in `state.json.checkpoint.blockers`.

**9b. state.json.** Advance `execution.active_unit`, `last_completed_unit`, `next_unit`. **Increment `session_count` by 1 (one turn, regardless of batch size).** `checkpoint.next_action` MUST include the `unit_id` that `select_next_unit.py` returns next so the Claude Code stop hook's agreement check passes.

**9c. Phase Completion Review.** If this turn marked the last unit of a phase completed: read `.harness/pr-review-checklist.md`, verify each item; if the phase is deploy-affecting run the deployment verifier from `config.json` (missing or failing verifier → blocker, stop). Only after the checklist + deploy gate pass: mark the phase `"completed"` in phase-graph.json.

**9d. checkpoint.md.** Refresh Last Completed / What Failed / What Is Next / Blocked By / Evidence / Open Questions.

## 10. Commit

Check for installed skills:
```bash
ls $GLOBAL_SKILLS_DIR/commit-agent-changes/SKILL.md 2>/dev/null || ls $WORKSPACE_SKILLS_DIR/commit-agent-changes/SKILL.md 2>/dev/null
ls $GLOBAL_SKILLS_DIR/code-review/SKILL.md 2>/dev/null || ls $WORKSPACE_SKILLS_DIR/code-review/SKILL.md 2>/dev/null
```

**Parallel dispatch at phase close.** When this turn closed a phase (9c marked the phase completed) AND **both** `code-review` and `commit-agent-changes` are installed, dispatch them **in one assistant message** with two `Agent(subagent_type: "general-purpose")` tool calls — one runs `code-review` read-only on the branch diff, the other runs `commit-agent-changes` to commit pending changes, push, and open or update the phase PR. Wait for both reports; resolve any High/Medium code-review findings in the main context and re-push. Disjoint state (read vs. write non-overlapping files) — they cannot conflict.

**Fallback.** When no phase closed this turn or only one of the two skills is installed, delegate commit/PR creation to `commit-agent-changes` alone; `code-review` (if installed) runs after the PR exists.

## 11. Turn Ends

The stop hook (`continue-loop.py`) fires automatically. It checks `.harness/.invoke-active` first — absent ⇒ hook is a no-op. Present ⇒ it checks loop budget, blockers, open questions, and runs `select_next_unit.py` to determine whether to continue. When it decides to stop, it deletes the flag.

**Claude Code note (ISSUE_002).** Claude Code's Stop hook has a one-shot `stop_hook_active` guard that caps hook-driven continuations at 1. For multi-turn autonomous runs, use **`/loop /invoke-development-harness`** instead of relying on the stop hook to chain turns. The stop hook's authority-chain checks remain useful as a per-turn precondition gate. Cursor's hook works as originally designed.

Do NOT manually loop.
