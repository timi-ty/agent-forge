# Harness Architecture Reference

## Purpose

The harness is a project-local control plane that compiles ROADMAP.md into phased, validator-backed autonomous execution. It orchestrates development work through deterministic phases and units, with validation at each checkpoint.

## File Layout

| Artifact | Purpose |
|----------|---------|
| `state.json` | Runtime snapshot of current phase, unit, progress, blockers |
| `config.json` | Harness configuration (git policy, deployment verifier, etc.) |
| `manifest.json` | Inventory of harness-owned files and managed blocks |
| `phase-graph.json` | Canonical phase/unit ordering and dependencies |
| `checkpoint.md` | Human-readable summary of current state and next action |
| `ARCHITECTURE.md` | This document (generated from `architecture.md` during `create`) |
| `scripts/` | Harness executables (select_next_unit.py, validate_harness.py, etc.) |
| `plans/` | Generated execution plans |
| `issues/` | Tracked blockers and open questions |
| `PHASES/` | Phase documents (PHASE_XXX_slug.md) |
| `.cursor/commands` | Workspace commands that invoke harness |
| `.cursor/hooks` | Stop hook for invoke continuation (`continue-loop.py`) |
| `.cursor/rules/harness-*` | Rule files for agent behavior |

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

The invoke loop uses a stop hook (`continue-loop.py`) that:

1. Reads `state.json`
2. Runs `select_next_unit.py`
3. Compares selector output with checkpoint consensus
4. **Continue** if deterministic selector and checkpoint agree on next action
5. **Stop** if they disagree
6. **Stop** if blockers or open questions exist

## Git Integration

Each completed unit results in a commit following `config.json` git policy. Check for commit-agent-changes skill; if installed, delegate. If not, commit directly.

## Deployment Truth

No deploy-affecting phase may be marked complete without a configured deployment verifier. Local success is confidence; deployed verification is truth. If deployment verifier is not configured, deploy-affecting phases are blocked.

## Phase Completion Review

Before a phase is marked complete, run internal review using `pr-review-checklist.md`.

## Skills Discovery

The harness checks for installed Cursor skills (code-review, commit-agent-changes) and uses them when available. If not installed, handles tasks inline.
