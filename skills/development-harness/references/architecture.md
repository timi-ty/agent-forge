# Harness Architecture Reference

## Purpose

The harness is a project-local control plane that compiles ROADMAP.md into phased, validator-backed autonomous execution. It orchestrates development work through deterministic phases and units, with validation at each checkpoint. Works with both Cursor and Claude Code.

## File Layout

The harness generates artifacts in tool-specific directories. `$TOOL_DIR` refers to `.cursor` (Cursor) or `.claude` (Claude Code).

| Artifact | Purpose |
|----------|---------|
| `state.json` | Runtime snapshot of current phase, unit, progress, blockers |
| `config.json` | Harness configuration (git policy, deployment verifier, detected tool, etc.) |
| `manifest.json` | Inventory of harness-owned files and managed blocks |
| `phase-graph.json` | Canonical phase/unit ordering and dependencies |
| `checkpoint.md` | Human-readable summary of current state and next action |
| `.invoke-active` | Transient flag file created by invoke, checked by stop hook (not committed) |
| `ARCHITECTURE.md` | This document (generated from `architecture.md` during `create`) |
| `scripts/` | Harness executables (select_next_unit.py, validate_harness.py, etc.) |
| `plans/` | Generated execution plans |
| `issues/` | Tracked blockers and open questions |
| `PHASES/` | Phase documents (PHASE_XXX_slug.md) |
| `$TOOL_DIR/commands/` | Workspace commands that invoke harness |
| `$TOOL_DIR/hooks/` | Stop hook for invoke continuation (`continue-loop.py`) |
| `$TOOL_DIR/rules/harness-*` | Rule files for agent behavior |

## Data Authority

- **state.json**: Runtime snapshot only. Ephemeral; reflects current execution state.
- **phase-graph.json**: Canonical source for phase/unit truth. Defines ordering and dependencies.
- **select_next_unit.py**: Authoritative "what to do next" source. Deterministic selector.
- **checkpoint.md**: Human-readable summary. Used for human verification; must agree with selector output.

## Ownership Model

Three classes of ownership govern what the harness controls vs. what the project owns:

- **harness-owned**: Created and fully controlled by the harness. `/clear` removes these.
- **product-owned**: May be scaffolded by harness during create; immediately become project responsibility. `/clear` never touches these.
- **managed-block**: Content injected into pre-existing files via markers. `/clear` removes only the marked block.

See `ownership-model.md` for full details.

## Validation Hierarchy

Seven layers of validation apply before phases are marked complete:

1. Static checks (linter, type checker, formatter)
2. Unit tests
3. Integration tests
4. E2E / browser / workflow tests
5. CI checks (GitHub Actions)
6. Deployed smoke checks (health endpoint, smoke test URL)
7. Deployed E2E (full E2E against deployed environment)

No phase is complete until applicable layers have evidence. See `validation-hierarchy.md` for details.

## Loop Mechanics

The invoke loop uses a stop hook (`continue-loop.py`) that is gated by a session flag file:

**Session gating:** The invoke command creates `.harness/.invoke-active` as its very first step. The hook checks for this flag before any other logic. If the flag is absent, the hook returns a no-op response. This prevents the hook from hijacking non-harness agent sessions (e.g. running "sync skills" or other unrelated commands in the same workspace).

When the flag is present, the hook proceeds with its authority chain:

1. Checks `.harness/.invoke-active` exists (session gate)
2. **Cursor:** Checks status is "completed"; **Claude Code:** Checks `stop_hook_active` is false
3. Reads `state.json` for loop budget, blockers, open questions
4. Runs `select_next_unit.py`
5. Compares selector output with checkpoint consensus
6. **Continue** if deterministic selector and checkpoint agree on next action
7. **Stop** if they disagree
8. **Stop** if blockers or open questions exist

**Cursor hook protocol:** Returns `{"followup_message": "..."}` to continue, `{}` to stop.
**Claude Code hook protocol:** Exits with code 2 + `{"decision": "block"}` to continue, exits with code 0 to stop.

When the hook decides to stop (for any reason), it deletes `.harness/.invoke-active` to reset the gate for the next session. When continuing, the flag is left in place.

## Batch Semantics — one turn per batch

Since PHASE_007's invoke-command rewrite, a single invoke turn processes a whole **batch** (not a single unit). A batch is the output of `compute_parallel_batch.py` over the current frontier; it carries one or more units. `commands/invoke.md` implements a single batch-driven pipeline in which only Steps 5 and 6 branch on batch size — everything else (compute / verify / merge / state / commit) is single-flow.

**`execution.session_count` increments by exactly 1 per turn, regardless of batch size.** Whether the batch held 1 unit (in-tree fast path) or N units (worktree fan-out via `Agent(subagent_type: "harness-unit")`), the stop hook sees one session tick; `loop_budget` is denominated in turns, not in units. The fleet-mode transition `idle → dispatched → merging → idle` also completes within a single turn in the worktree path; the hook never sees a partial fleet.

See `commands/invoke.md` Steps 4–9 for the pipeline and PHASE_007's rewrite rationale; see `parallel-execution.md` for the dispatch lifecycle and conflict-strategy catalogue.

## Parallel Execution Model

A single invoke turn can fan out across multiple units when `config.execution_mode.parallelism.enabled` is true. This section summarises the moving parts; the full lifecycle lives in `parallel-execution.md` (unit_047).

### When to enable parallelism

Parallelism is opt-in per project via `config.json`:

```json
"execution_mode": {
  "parallelism": {
    "enabled": true,
    "max_concurrent_units": 3,
    "conflict_strategy": "abort_batch",
    "require_touches_paths": true,
    "allow_cross_phase": false
  }
}
```

A unit is a candidate for parallel batching only when it declares `parallel_safe: true` AND its `depends_on` predecessors are all `completed` AND (when `require_touches_paths: true`) it carries a non-empty `touches_paths` glob list. Leave parallelism off on small projects, greenfield scaffolding phases, or any phase whose units share the same files. Turn it on once phases routinely contain 3+ independent units.

### Worktree-per-unit layout

Each unit in a parallel batch gets its own git worktree at `.harness/worktrees/<batch_id>/<unit_id>/` on a dedicated branch `harness/<batch_id>/<unit_id>` (created off `HEAD` at dispatch time). `dispatch_batch.py` seeds `<worktree>/.harness/WORKTREE_UNIT.json` with the unit's identity (`batch_id`, `unit_id`, `phase_id`, `touches_paths`) — this sentinel is the sub-agent's binding to its scope and is the source-of-truth for merge-time scope enforcement. Worktrees are harness-owned and gitignored.

### Orchestrator / sub-agent boundary

The main agent is the **orchestrator**. It never edits files inside a worktree directly. For each unit in the batch it dispatches exactly one `Agent(subagent_type: "harness-unit")` call, handing over the unit's identity. The sub-agent runs under a tight allowlist (see `templates/claude-code/agents/harness-unit.md`):

- Writes allowed **only** inside its own worktree; no writes to `.harness/` or to other units' worktrees.
- No `git push`, `git merge`, `git rebase`, or branch manipulation beyond commits on the unit's own branch.
- Must emit a structured JSON report at end-of-turn describing status + commits + validation evidence.

The sub-agent's self-report is **never** trusted for blast radius. The orchestrator's merge step runs the scope check against the git diff.

### Frontier + overlap check

`select_next_unit.py --frontier` emits every unit whose dependencies are satisfied. `compute_parallel_batch.py` greedy-packs the frontier into the largest batch that respects:

1. `parallel_safe: true` on every accepted unit.
2. `require_touches_paths: true` enforcement (reject units with empty `touches_paths` if the flag is on).
3. `max_concurrent_units` cap.
4. `allow_cross_phase: false` (default) — batch is restricted to a single phase once the first unit is accepted.
5. **Overlap matrix** — unit A and unit B may share a batch only if their `touches_paths` globs are `fnmatch`-disjoint. Overlapping units are rejected with reason `touches_overlap: <other_unit_id>`.

The result is a `{batch_id, batch, excluded}` record; the orchestrator consumes `batch`, `excluded` is reported for observability.

### Dispatch → wait → merge lifecycle

A parallel turn moves `state.execution.fleet.mode` through three states and returns to `"idle"` within the same turn:

1. **`idle` → `dispatched`.** `dispatch_batch.py` creates all worktrees + branches, writes `WORKTREE_UNIT.json` into each, appends `status: "running"` entries to `fleet.units`. Atomic on failure — any per-unit error tears down every worktree created in the same call.
2. **`dispatched` (stays here while sub-agents run).** The orchestrator dispatches all `Agent(subagent_type: "harness-unit")` calls in a single assistant message and waits for every report. Hygiene checks on each report (unit_id matches, `status ∈ {succeeded, failed}`, `commits` non-empty on success) reject malformed reports as `category: "infrastructure"`.
3. **`dispatched` → `merging` → `idle`.** `merge_batch.py` serially merges each unit's branch back onto `HEAD` with `--no-ff`. Every unit's changed files are scope-checked against its declared `touches_paths` BEFORE the merge attempt; scope violators are hard-rejected with `category: "scope_violation"`. Clean merges flip the unit to `status: "merged"` and remove the worktree + branch. Conflict handling follows the configured `conflict_strategy`.

The stop hook never sees a partial fleet — `fleet.mode != "idle"` at turn-end means the previous turn crashed mid-batch and recovery goes through `/sync-development-harness`.

### Conflict strategies

Two strategies live in `config.execution_mode.parallelism.conflict_strategy`:

- **`abort_batch` (default).** First merge conflict aborts the batch: the conflicting unit is marked `status: "failed"` with `conflict.category: "merge_conflict"`, every remaining unit is marked `status: "failed"` with `conflict: null` (skipped, not conflicted), and the turn stops. Safe default — guarantees a clean `HEAD` and forces manual resolution.
- **`serialize_conflicted`.** The conflicting unit stays `status: "running"` (worktree + branch preserved) and the orchestrator continues merging the remaining units. Deferred units retry on a later batch. Documented but not default; enables "make progress on what you can, retry the rest" for long batches where individual conflicts are expected.

Scope violations are always hard rejects regardless of strategy — `touches_paths` is a trust-boundary declaration (see `phase-contract.md` "Scope-Violation Enforcement Policy").

### Merge serialization via `.harness/.lock`

`merge_batch.py` wraps its entire flow in an `O_EXCL` file mutex at `.harness/.lock` so two concurrent invocations cannot interleave merges. Second acquirers block until the first releases; stale locks (mtime past `lock_stale_after`, default 600s) are forcibly taken over to prevent deadlock after a crashed holder.

### Safety rails — session kill switch

Two `scope_violation` or `ambiguity` failures in a single invoke session write `.harness/.parallel-disabled` via `safety_rails.py`. The invoke flow reads this flag at the start of each turn and forces the in-tree fast path for the remainder of the session regardless of `config.execution_mode.parallelism.enabled`. The flag is cleared by the stop hook when `.invoke-active` is cleared, so the next session starts fresh. See `commands/invoke.md` Step 4 for the read path.

### Observability

Each parallel turn writes artifacts under `.harness/logs/<batch_id>/`:

- **`batch.json`** — full batch plan + overlap analysis + dispatched fleet. Written by `dispatch_batch.py`.
- **`<unit_id>.md`** — sub-agent summary. Written by the sub-agent per the harness-unit contract.
- **`merge.log`** — grep-friendly summary of per-unit merge outcomes. Written by `merge_batch.py`.
- **`validation.log`** — post-merge validator output. Written by `merge_batch.py`.

All writes are best-effort (helpers + call sites wrap in try/except); a log failure never blocks dispatch or merge. `/harness-state` renders these alongside `fleet` and `sync_harness.py` orphan detection (see `commands/state.md`).

## Git Integration

Each completed unit results in a commit following `config.json` git policy. Check for commit-agent-changes skill; if installed, delegate. If not, commit directly.

## Deployment Truth

No deploy-affecting phase may be marked complete without a configured deployment verifier. Local success is confidence; deployed verification is truth. If deployment verifier is not configured, deploy-affecting phases are blocked.

## Phase Completion Review

Before a phase is marked complete, run internal review using `pr-review-checklist.md`.

## Skills Discovery

The harness checks for installed skills (code-review, commit-agent-changes) in the appropriate paths for the detected tool and uses them when available. If not installed, handles tasks inline.
