# Harness Checkpoint

## Last Completed
**unit_029 (PHASE_007):** The big one. [commands/invoke.md](skills/development-harness/commands/invoke.md) rewritten **whole-file** from 432 → 332 lines into a single **batch-driven 12-step pipeline**. Zero "sequential path vs parallel path" fork language remains — grep confirms.

### The new 12-step structure (0–11)

- **Steps 0–3** — Detect Host Tool → Activate Invoke Session → Validate → Load State. Step 3 gains a new `fleet.mode != "idle"` guard so we stop-and-`/sync` if a previous turn died mid-batch.
- **Step 4** — Compute Batch via `select_next_unit.py --frontier` piped into `compute_parallel_batch.py`. Output drives the rest of the turn. "Pick the dispatch mode" sub-section: **in-tree fast path** when `len(batch) == 1 && parallelism.enabled == false`; **worktree fan-out** otherwise (including `len == 1` with parallelism on, to support the PHASE_009 batch-of-1 regression test).
- **Step 5 — Dispatch** — the only top-level branch in the flow:
  - **In-tree:** current working tree is the worktree; fleet.mode stays `"idle"`.
  - **Worktree fan-out:** `dispatch_batch.py` creates worktrees + branches + `WORKTREE_UNIT.json`, flips fleet.mode to `"dispatched"`.
- **Step 6 — Execute** — the second top-level branch:
  - **In-tree:** inline implementation with the preserved capabilities from earlier phases — optional `Agent(Explore)` on refactor/extend/fix/migrate/update keywords (unit_011), multi-file parallel-edit guidance for ≥4 independent files (unit_013), parallel Layer 1 + Layer 2 validation when the config flag is on (unit_016).
  - **Worktree fan-out:** one `Agent(subagent_type: "harness-unit")` per unit in a **single assistant message**; the agent template (unit_026) carries the full contract; briefing hands over identity only. Sub-agents return JSON reports; `merge_batch.py`'s scope check (unit_022) is still the merge gate — self-reports are never trusted for blast radius.
- **Step 7 — Verify** — scope-violation check (in-tree: `git diff --name-only` vs declared `touches_paths`) + report-hygiene checks on sub-agent reports (unit_id match, status/failure consistency, commits non-empty on success). Violations → force `status: "failed"` with category.
- **Step 8 — Merge** — **no-op for in-tree** (changes already on the current branch); **`merge_batch.py`** for worktree fan-out (acquires `.harness/.lock`, flips mode to `"merging"`, scope-check + serial fan-in + post-merge validation + rollback-on-failure + worktree/branch cleanup, mode → `"idle"`).
- **Step 9 — State Update & Phase Completion** — 4 sub-steps:
  - **9a** phase-graph.json: completed units → `"completed"`, failed units stay `"pending"` (blockers live in state.json, not phase-graph).
  - **9b** state.json: `session_count` **increments by 1 per turn regardless of batch size**; `checkpoint.next_action` must include `select_next_unit.py`'s `unit_id` so the stop-hook agreement check passes.
  - **9c** Phase Completion Review: checklist + deployment gate, only then mark phase `"completed"`.
  - **9d** checkpoint.md refresh.
- **Step 10 — Commit** — at phase close with both skills installed, dispatches `code-review` + `commit-agent-changes` **in one assistant message** (unit_032 acceptance pre-satisfied); serial fallback when one skill is missing or no phase closed.
- **Step 11 — Turn Ends** — stop-hook authority chain documented; includes an explicit **ISSUE_002 note** pointing Claude Code users at `/loop /invoke-development-harness` as the multi-turn driver since the Stop hook's `stop_hook_active` guard caps continuations at 1. Cursor behaviour is unchanged.

### Capability preservation
Every capability introduced in earlier phases still lives in the rewritten doc, just in a different location:

| Origin | New home |
|--------|----------|
| unit_011 Exploration step | Step 6 in-tree path |
| unit_013 multi-file parallel edits | Step 6 in-tree path |
| unit_014 parallel phase-review dispatch | Step 10 Commit |
| unit_016 parallel Layer 1 + Layer 2 validation | Step 6 in-tree path |
| unit_018 per-layer timing in evidence | Step 6 in-tree path + Step 9b checkpoint.next_action semantics |
| unit_022 scope-violation detector | Step 8 Merge (worktree fan-out) + Step 7 Verify (in-tree path) |
| unit_023 `.harness/.lock` mutex | Step 8 Merge |
| unit_026 harness-unit agent template | Step 6 worktree fan-out |
| unit_027 orchestrator boundary rules | referenced implicitly throughout Steps 5–10 |

## What Failed (if anything)
None.

## What Is Next
**Complete unit_030 (PHASE_007):** Mirror the rewritten batch-driven flow into [templates/workspace-commands/invoke-development-harness.md](skills/development-harness/templates/workspace-commands/invoke-development-harness.md). Wording consistent with the command-doc version — same 12-step numbering, same in-tree vs worktree fan-out branching in Steps 5/6, same fleet.mode transitions, same single-assistant-message `Agent(harness-unit)` dispatch.

## Blocked By
None.

## Evidence
- [skills/development-harness/commands/invoke.md](skills/development-harness/commands/invoke.md): whole-file rewrite, 332 lines (down from 432).
- Grep: zero "sequential path" / "parallel path" matches; `fleet.mode` transitions present at Steps 3 / 5 / 8 / 11; every `## Step N` heading 0 → 11 present exactly once.
- `python -m unittest discover skills/development-harness/scripts/tests` → 171/171 pass (docs-only change; test suite unchanged).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot; the rewritten invoke.md Step 11 now explicitly points Claude Code users at `/loop /invoke-development-harness`. Skill-source fix still scheduled as `unit_bugfix_002` at the head of PHASE_011 (this turn's doc update acknowledges the workaround; the fix that removes the hook as a continuation-driver is separate).

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_007 PR opens after unit_033 (the integration test closes the phase).
- **Branch:** `feat/phase-007-invoke-rewrite`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 29 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_007 progress: **1/5 units done**. Remaining: 030 template mirror, 031 architecture.md one-turn-per-batch paragraph, 032 parallel phase-review dispatch (already pre-satisfied by unit_029's Step 10 — this unit becomes a grep-verify formality), 033 integration test `test_invoke_rewrite`.
- Test-suite count unchanged at 171 (docs-only so far in PHASE_007).

---
*Updated: 2026-04-20T04:05:00Z*
