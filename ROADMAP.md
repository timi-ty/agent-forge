# Development Harness — Multi-Agent Upgrade

This roadmap compiles into a development-harness phase plan that upgrades the `development-harness` skill to support multi-agent parallel execution.

**Target skill:** `skills/development-harness/` in this repo.

**Goal:** Add worktree-isolated unit-level parallelism, intra-unit helper-agent delegation, and parallel validation — all opt-in per harness, cleanly versioned via a schema bump, and enforced by structural trust boundaries rather than agent self-reporting.

**Non-goals:**
- Cross-phase parallel execution (gated off until unit-level parallelism is proven).
- Speculative execution of units with in-flight dependencies.
- Distributed or multi-machine agent execution.
- Automatic inference of a unit's `touches_paths` from static analysis.
- Backward compatibility with v1 harness data shapes. A `schema_version` bump means re-running `/create-development-harness`; no migration code is provided.

**Design principles that apply across every phase:**
1. Parallelism is opt-in per harness via `config.parallelism.enabled`. Units without required parallelism metadata fail validation rather than silently falling back to serial execution.
2. Worktrees are the isolation unit. One parallel unit = one `Agent(isolation: …)` call = one branch to merge.
3. Dispatch–wait–merge completes inside a single invoke turn. The stop hook's authority chain is unchanged.
4. The orchestrator is the only process that merges, updates canonical harness state, and touches `.harness/`. Sub-agents are confined to their worktree.
5. A unit must declare `touches_paths` to be eligible for a parallel batch. Opaque units run serial.
6. Trust is structurally verified: after a sub-agent reports, the orchestrator diffs the branch against declared paths and rejects scope violations.

---

## Schema and Data Model

Extend the harness data model to express unit-level dependencies, blast radius, parallelism opt-outs, and fleet runtime state. Introduces a breaking schema change; downstream phases consume these fields.

**Scope:**
- Add `depends_on`, `touches_paths`, `parallel_safe` to the unit object in `schemas/phase-graph.json`.
- Add `execution.fleet` section to `schemas/state.json` with `mode`, `batch_id`, and per-unit fleet entries (worktree path, branch, status, conflict metadata, agent summary path).
- Add `execution_mode.parallelism` to `schemas/config.json` (`enabled`, `max_concurrent_units`, `conflict_strategy`, `require_touches_paths`, `allow_cross_phase`).
- Add `execution_mode.agent_delegation` to `schemas/config.json` (`use_explore_for_research`, `use_code_review_skill_for_phase_review`, `parallel_validation_layers`).
- Add `execution_mode.versioning` to `schemas/config.json` (`break_on_schema_bump: bool`). Captures the user's stance on harness-version back-compat, answered during `/create-development-harness` Phase 2. When `true`, schema mismatches emit the re-create error; when `false`, the harness surfaces the mismatch and defers to user-authored migration guidance. Default `true`.
- Register `.harness/worktrees/` and `.harness/logs/` as harness-owned transient directories in `schemas/manifest.json` and the `.gitignore` template.
- Bump `SCHEMA_VERSION` in `scripts/harness_utils.py` from `"1.0"` to `"2.0"`.

**Breaking changes:**
- `depends_on` is **required** on every unit. A unit with no deps declares `"depends_on": []`.
- `touches_paths` is **required** when `parallel_safe: true`; validator rejects `parallel_safe: true` without it.
- `validate_harness.py` rejects any harness with `schema_version: "1.0"` and emits an actionable error instructing the user to re-run `/create-development-harness`. No migration path is provided.

**Validation:**
- `validate_harness.py` extended to check new fields structurally: required-field enforcement (no inference); `depends_on` entries must reference sibling unit IDs in the same phase; no cycles; `touches_paths` rejects `..` and absolute paths; `parallel_safe` is bool; `fleet.mode` is one of the documented enums; fleet unit IDs exist in phase-graph; version gate emits the re-create error on mismatch.
- Unit tests for every new validation rule, including rejection of v1 fixtures.

## Frontier Selector and Batch Computation

Replace "pick one next unit" with a frontier model that can also pick a safe parallel batch. Introduces no runtime behavior change until the invoke command is rewritten in a later phase.

**Scope:**
- Rewrite `scripts/select_next_unit.py` around frontier computation. Add `--frontier` and `--max N` flags for batch consumers; without flags the script returns the head of the frontier (preserves the stop hook's JSON contract). No legacy list-order fallback.
- Frontier semantics: a unit is ready iff its phase is unblocked AND every unit in its `depends_on` is `completed`. Malformed units (validator would have caught these upstream) cause the selector to error loudly, not paper over the problem.
- New script `scripts/compute_parallel_batch.py`: consumes the frontier, applies policy (`parallel_safe`, `require_touches_paths`), runs the glob-overlap matrix (stdlib `fnmatch` only), greedy-packs under `max_concurrent_units`, and emits `{batch, excluded, batch_id}`.
- Glob overlap rule: two units conflict if any pair of their declared globs overlap OR if any literal prefix of one matches the other.
- Exclusion reasons are machine-readable strings: `"not_parallel_safe"`, `"path_overlap_with:<unit_id>"`, `"capacity_cap"`.

**Validation:**
- Unit tests for frontier selection on linear, diamond, disconnected, and partially-completed graphs.
- Unit tests for batch computation: same path, glob vs literal, nested globs, `max_concurrent_units` enforcement, `require_touches_paths` enforcement.
- Existing single-unit callers (stop hook, invoke command) must continue to pass all current tests.

## Intra-Unit Helper-Agent Delegation

Adopt multi-agent workflows inside a single unit — no worktree infrastructure, immediate speed wins, applicable to both sequential and (future) parallel paths.

**Scope:**
- Insert an Exploration step in both `commands/invoke.md` and `templates/workspace-commands/invoke-development-harness.md`. When the unit description implies modifying existing systems (refactor, extend, fix, migrate, update), dispatch `Agent(subagent_type: "Explore", thoroughness: "medium")` before implementation.
- Add "multi-file parallel edits" guidance: when the implementation plan touches ≥4 independent files, fan out to 2–3 `Agent(general-purpose)` calls in a single message. Only when edits are genuinely independent.
- During phase completion review, when the `code-review` skill is installed, dispatch it via `Agent` concurrently with the `commit-agent-changes` draft step (currently these run sequentially).
- Update `templates/claude-code/rules/harness-core.md` with guidance on when to delegate vs. handle inline.

**Validation:**
- Self-consistency: the instructions correctly distinguish "parallel" (single message, multiple tool calls) from "sequential" dispatch.
- No changes to harness state scripts in this phase.

## Parallel Validation Layers

Collapse validation wall-clock time by running independent layers concurrently. Orthogonal to unit-level parallelism.

**Scope:**
- Rewrite the validation step in `commands/invoke.md` and the workspace template: when `config.agent_delegation.parallel_validation_layers == true`, run Layer 1 (lint + typecheck + formatter) and Layer 2 (unit tests) as concurrent `Bash` calls in a single message.
- Layer 3 (integration) and Layer 4 (E2E) remain serial — they commonly contend on ports, fixtures, and DB state.
- Collect all exit codes; the unit passes only if every parallel layer passes.
- Evidence format updated to record per-layer timing (e.g., `"pnpm lint exits 0 (2.1s)"`) so the benefit is visible in checkpoint history.

**Validation:**
- Manual/example walkthrough on a sample project showing parallel layer execution.
- The evidence-recording rule must survive: no "tests pass" — every layer's command and exit code are captured.

## Worktree Dispatch and Merge Infrastructure

Build the mechanics of a parallel batch without yet wiring them into the invoke command. Everything is invocable from the command line and fully unit-tested before it reaches the live invoke flow.

**Scope:**
- New script `scripts/dispatch_batch.py`: takes a batch JSON, creates `git worktree`s under `.harness/worktrees/<batch_id>/<unit_id>`, creates branches `harness/<batch_id>/<unit_id>`, seeds each worktree with `.harness/WORKTREE_UNIT.json` (batch_id, unit_id, phase_id, declared touches_paths), updates `state.json.execution.fleet`. Atomic on failure — partial worktrees are torn down on any error.
- New script `scripts/merge_batch.py`: serial fan-in. Per unit, run `git merge --no-ff harness/<batch_id>/<unit_id>`. On conflict, `git merge --abort`, record conflicting paths on the unit's fleet entry, apply `conflict_strategy`:
  - `abort_batch`: abort remaining merges, tear down worktrees, mark batch failed.
  - `serialize_conflicted`: continue merging clean branches, requeue conflicted units as pending with conflict metadata.
- After all merges succeed, run post-merge validation (repo-wide lint + typecheck + each merged unit's unit tests, in parallel). On failure, `git reset --hard <pre-merge-ref>` and mark batch failed.
- New script `scripts/teardown_batch.py`: idempotent cleanup for orphaned worktrees and `harness/batch_*` branches. Used by `/clear`, `/sync`, and error recovery.
- Scope-violation check: orchestrator computes `git diff --name-only <merge-base>..<branch>` and rejects any unit whose diff exceeds declared `touches_paths`. This runs *before* merge. The agent's self-report is never trusted for blast radius.
- `.harness/.lock` mutex around `merge_batch.py` to prevent concurrent merges if two invoke sessions somehow collide.
- `scripts/sync_harness.py` extended to detect orphaned worktrees, stale fleet entries, and `harness/batch_*` branches without fleet entries.

**Validation:**
- Integration test `scripts/tests/integration/test_parallel_invoke.sh`: sets up a tmp git repo with a 3-unit phase, runs dispatch/merge using shell-scripted fake agents that commit canned files. Asserts final state and cleanup.
- Unit tests for conflict paths (both strategies), scope-violation rejection, lock contention, teardown idempotency.
- Manual verification: `dispatch_batch.py` + `merge_batch.py` succeed on a real small-scale batch.

## Orchestrator Agent Contract

Define the sub-agent's job, tool allowlist, and structured report so orchestration becomes a verifiable contract rather than free-form delegation.

**Scope:**
- New agent definition `templates/claude-code/agents/harness-unit.md`: system prompt, tool allowlist (no `git push`, no writes to `.harness/`, no writes outside worktree), hard rules, required report schema.
- Required report schema (returned as final message from the sub-agent):
  ```
  {
    "unit_id": "…",
    "status": "succeeded" | "failed",
    "validation_evidence": ["…"],
    "commits": ["<sha>", …],
    "touched_paths_actual": ["…"],
    "failure": null | {"category": "validation" | "scope_violation" | "ambiguity", "detail": "…"}
  }
  ```
- Update `templates/claude-code/rules/harness-core.md` with rules: only the orchestrator modifies `.harness/` or runs `git merge`; sub-agents commit only within their worktree branch; sub-agents never push or rebase; a worktree containing `.harness/WORKTREE_UNIT.json` is a fan-out environment and must follow the harness-unit contract.
- Mirror rules for Cursor where applicable.

**Validation:**
- Review: the agent definition is self-contained (a fresh sub-agent with only the briefing can execute).
- The report schema is documented in `references/parallel-execution.md` (added in the Docs phase).

## Invoke Command Rewrite

Collapse the invoke flow into a single batch-driven pipeline. A batch of 1 runs in-tree (no worktree), a batch of N fans out — same code path, same checkpoints, same state transitions.

**Scope:**
- Rewrite `commands/invoke.md` and `templates/workspace-commands/invoke-development-harness.md` into a single flow:
  - Step 0–3: unchanged.
  - Step 4: compute batch via `compute_parallel_batch.py`. The batch is always produced; it may contain 1 unit or N units depending on frontier + `parallelism.enabled` + overlap analysis.
  - Step 5 — dispatch:
    - If batch size == 1 and `parallelism.enabled == false`: skip worktree setup; the current working tree is the "worktree" for the single unit. All subsequent steps still run.
    - Otherwise: `dispatch_batch.py` creates per-unit worktrees and fan-out briefings.
  - Step 6 — execute:
    - If in-tree (size 1 + parallelism disabled): execute the unit inline.
    - Otherwise: emit one `Agent` tool call per unit **in a single assistant message** with `subagent_type: "harness-unit"`, a self-contained briefing (worktree path, phase excerpt, unit row, rules), and the expected report schema.
  - Step 7 — verify: for every unit's resulting diff, run scope-violation check; if violated, force `failed` with category `scope_violation` regardless of what was reported.
  - Step 8 — merge: `merge_batch.py` (no-op for the in-tree single-unit case; performs actual merges for worktree batches).
  - Step 9 — state: update `state.json` and `checkpoint.md`. Successful units → `completed`. Failed/conflicted units → `pending` with blocker entry. Set `fleet.mode = "idle"`. `checkpoint.next_action` is populated via `select_next_unit.py` (no-flag mode) so the stop hook's agreement check continues to work.
  - Step 10 (commit) and Step 11 (turn ends) unchanged.
- One turn = one batch. `session_count` increments once per turn regardless of batch size. Document this in `references/architecture.md`.
- Phase-completion review (Step 9 of the legacy flow) dispatches `code-review` skill concurrently with commit prep when both are installed.

**Validation:**
- End-to-end run on a 3-unit fixture phase with `parallelism.enabled = true`: dispatch, merge, state updates, stop-hook continuation all succeed.
- Batch-of-1 path: in-tree execution produces the same final state as a worktree batch would (unit completed, evidence recorded, checkpoint updated, one commit).
- Failure modes exercised: scope violation, merge conflict (both strategies), post-merge validation failure.

## Stop-Hook Fleet Awareness

Make the loop guard safe under parallel execution. Without this, a crashed mid-batch turn could cause the hook to continue into an inconsistent state.

**Scope:**
- Update `templates/claude-code/hooks/continue-loop.py` and `templates/hooks/continue-loop.py` (Cursor): add a pre-check — if `state.execution.fleet.mode != "idle"`, treat as ambiguity and stop.
- Stop-hook tests: simulated `fleet.mode = "dispatched"` must cause exit 0 (stop); `"idle"` preserves existing behavior.
- Reconciliation: when the hook stops due to in-flight fleet, it deletes `.invoke-active` so the next session starts clean. Document that recovery requires `/sync-development-harness` to detect orphans.

**Validation:**
- Unit tests for both hook implementations (Claude Code and Cursor).
- Manual test: kill an invoke turn mid-batch and confirm the hook stops on the next invocation and surfaces the orphan via `/sync`.

## Safety Rails and Automatic Fallback

Add the degradation paths that make parallelism safe to enable on real projects.

**Scope:**
- Session-scoped kill switch: if a batch fails with category `scope_violation` or `ambiguity` more than once in a single session, write `.harness/.parallel-disabled` and run the rest of the session sequentially. Cleared when `.invoke-active` is cleared.
- Auto-downgrade: when the frontier yields a batch of 1, silently use the sequential path (no special-case logging).
- Scope-violation enforcement is non-negotiable and always on, even when `require_touches_paths == false`. The declared-paths contract is the trust boundary.
- Default `conflict_strategy: "abort_batch"`. Document `serialize_conflicted` as advanced and not recommended for early adoption.
- Global mutex `.harness/.lock` guards `merge_batch.py` (already introduced in the dispatch phase; verified here).

**Validation:**
- Tests for the kill-switch behavior (two scope violations → sequential).
- Test: batch of size 1 silently runs sequential.
- Test: concurrent merge attempts are serialized by the lock.

## Observability

Make fleet state legible to humans without reading JSON.

**Scope:**
- Extend `templates/checkpoint-template.md` with a "Batch" section: batch ID, mode, per-unit status and branch, conflicts summary.
- Update `commands/state.md` and `templates/workspace-commands/harness-state.md` to render fleet status, orphaned worktrees (via `sync_harness.py --dry-run`), and per-batch timings.
- Orchestrator writes `.harness/logs/<batch_id>/`:
  - `batch.json` — full batch plan + overlap analysis.
  - `<unit_id>.md` — sub-agent's human-readable summary (written by the sub-agent).
  - `merge.log` — output from `merge_batch.py`.
  - `validation.log` — post-merge validation output.
- Logs are harness-owned, gitignored, retained until `/clear` or aged out.

**Validation:**
- Run a sample batch and confirm all log artifacts are produced.
- `/harness-state` output includes fleet and log pointers.

## Documentation

Make parallel execution discoverable, understandable, and safe to adopt.

**Scope:**
- `references/architecture.md` — new "Parallel Execution Model" section covering worktree-per-unit, orchestrator vs. sub-agent trust boundary, frontier + overlap check, dispatch–wait–merge lifecycle, conflict strategies, and when to enable vs. not.
- `references/phase-contract.md` — document the new unit fields (`depends_on`, `touches_paths`, `parallel_safe`) and add a "Decomposing a phase for parallelism" subsection with concrete guidance (feature-sliced units, narrow path declarations, avoiding shared-config units).
- New `references/parallel-execution.md` — full how-it-works reference: dispatch lifecycle diagram (text), overlap-matrix algorithm, merge-order rationale, failure-mode catalog, recovery procedures.
- Update `commands/create.md` Phase 2 to add two structured questions:
  1. "Enable parallel unit execution?" (y/n, default n) → `config.execution_mode.parallelism.enabled`.
  2. "When the harness's `schema_version` changes, should breaking changes require re-creating the harness, or do you want migration guidance?" (break / migrate, default break) → `config.execution_mode.versioning.break_on_schema_bump`. Asked as a first-class Phase 2 question (same format as merge strategy, review policy, etc.) so the user's stance is explicit and recorded, not assumed.
  3. Downstream behavior aligns with the answer: `validate_harness.py`'s version gate and `/update-development-harness`'s upgrade messaging both read this config field and behave accordingly.
- Update `commands/create.md` Phase 4 to instruct the agent to propose `touches_paths` per unit and set `parallel_safe: false` when blast radius is unknown.
- Update `SKILL.md` with a short "Parallel execution (optional)" subsection pointing to the reference doc.

**Validation:**
- Cross-check: every new field, script, rule, and command mentioned in this roadmap is documented in at least one reference.
- Walk-through test: a reader unfamiliar with the upgrade can enable parallelism using only the docs.

## Release Readiness

Make the schema bump safe to adopt by ensuring users know exactly what to do when they see the version mismatch error.

**Scope:**
- Add a "parallelism readiness checklist" section to `references/parallel-execution.md`: `touches_paths` declared on every parallelism-eligible unit, no pending unit modifies a shared aggregator file, CI can handle multi-commit pushes.
- Update `SKILL.md` with a "Version upgrades" note: when `schema_version` changes, users re-run `/create-development-harness`; `ROADMAP.md` and `PHASES/*.md` are untouched by the recreate flow. No migration script is provided, by design.
- Update `/update-development-harness` to detect a `schema_version` mismatch between the installed harness and the skill, and emit a pointer to the recreate flow.
- Default `config.parallelism.enabled = false`. Reason: users must decompose phases with `touches_paths` before parallelism is useful — not for back-compat.

**Validation:**
- `validate_harness.py` on a v1 fixture exits non-zero with the "re-run `/create-development-harness`" message (covered by PHASE_001 tests; re-asserted here with a dedicated fixture).
- `/update-development-harness` on a v1 installation produces the recreate pointer, not a silent migration.

## Harness Self-Test

Before declaring the upgrade complete, exercise it end-to-end on a non-trivial scenario to shake out integration issues the unit tests can't cover.

**Scope:**
- Create a throwaway test workspace with a realistic 2-phase / 6-unit roadmap (e.g., a mini CRUD app).
- Run `/create-development-harness`, enable parallelism, populate `touches_paths` on all units.
- Run `/invoke-development-harness` repeatedly until all phases complete, including at least one batch of size ≥2, one intentional merge conflict, and one intentional scope violation.
- Capture execution traces; verify:
  - Wall-clock improvement vs. a sequential run of the same roadmap.
  - All validation evidence is recorded correctly.
  - Conflict and scope-violation paths behaved as documented.
  - Stop-hook continuation and termination behaved correctly.
  - No orphaned worktrees or branches after completion.
- Document findings in a post-mortem under `.harness/logs/self-test/` and link from `references/parallel-execution.md`.

**Validation:**
- Self-test run is green end-to-end.
- Post-mortem identifies no blocker-level issues; any papercuts are filed as follow-up issues via `/inject-harness-issues`.
