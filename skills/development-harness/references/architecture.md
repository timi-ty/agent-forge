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

## Git Integration

Each completed unit results in a commit following `config.json` git policy. Check for commit-agent-changes skill; if installed, delegate. If not, commit directly.

## Deployment Truth

No deploy-affecting phase may be marked complete without a configured deployment verifier. Local success is confidence; deployed verification is truth. If deployment verifier is not configured, deploy-affecting phases are blocked.

## Phase Completion Review

Before a phase is marked complete, run internal review using `pr-review-checklist.md`.

## Skills Discovery

The harness checks for installed skills (code-review, commit-agent-changes) in the appropriate paths for the detected tool and uses them when available. If not installed, handles tasks inline.
