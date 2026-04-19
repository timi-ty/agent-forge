# Harness Architecture (agent-forge bootstrap)

## Purpose

This harness is a project-local control plane that compiles `ROADMAP.md` into phased, validator-backed autonomous execution. It orchestrates the **multi-agent upgrade of the `development-harness` skill itself** — dogfood. The skill source lives at `skills/development-harness/`; the harness runs work against that tree.

## Dogfood caveat

The skill being upgraded is also the skill this harness is built from. To keep the running harness stable while its own source is being rewritten:

- **Canonical skill source:** `skills/development-harness/` — phase work edits files here.
- **Frozen runtime copy:** `.harness/scripts/` — snapshot of the skill's scripts at bootstrap time. The running harness executes these, not the canonical source. They are intentionally stable until the next `/clear` + `/create`.

If early-phase changes wedge the harness, `/clear` followed by `/create` re-bootstraps from the latest skill source.

## File Layout

| Artifact | Purpose |
|----------|---------|
| `.harness/state.json` | Runtime snapshot (current phase, unit pointers, checkpoint, loop budget) |
| `.harness/config.json` | Harness configuration (git policy, tool, project metadata, execution mode) |
| `.harness/manifest.json` | Inventory of harness-owned files and managed blocks |
| `.harness/phase-graph.json` | Canonical phase/unit ordering, dependencies, statuses |
| `.harness/checkpoint.md` | Human-readable summary of current state and next action |
| `.harness/pr-review-checklist.md` | Phase completion review checklist |
| `.harness/.invoke-active` | Transient session flag checked by the stop hook (gitignored) |
| `.harness/scripts/` | Frozen copy of harness scripts (select_next_unit.py, validate_harness.py, etc.) |
| `.harness/plans/` | Generated execution plans |
| `.harness/issues/` | Tracked blockers and open questions |
| `PHASES/` | 13 phase documents (PHASE_001_…md through PHASE_013_…md) |
| `.claude/commands/` | 7 Claude Code slash commands for harness operations |
| `.claude/hooks/continue-loop.py` | Stop hook for invoke continuation |
| `.claude/rules/harness-*.md` | 5 rule files governing agent behavior |
| `.github/workflows/ci.yml` | CI workflow running harness unit tests on PR/push |
| `ROADMAP.md` | Product intent — authoritative; read-only after bootstrap |

## Data Authority

- **`state.json`:** Runtime snapshot only. Ephemeral; reflects current execution state.
- **`phase-graph.json`:** Canonical source for phase/unit truth. Defines ordering and dependencies.
- **`scripts/select_next_unit.py`:** Authoritative "what to do next" source. Deterministic selector.
- **`checkpoint.md`:** Human-readable summary. Must agree with selector output for the stop hook to continue.

## Ownership Model

- **harness-owned:** Created and fully controlled by the harness. `/clear` removes these. All `.harness/*`, `.claude/commands/*`, `.claude/rules/harness-*`, `.claude/hooks/continue-loop.py`, `PHASES/*`, `AGENTS.md`.
- **product-owned:** Scaffolded by harness during create; immediately project responsibility. `/clear` never touches these. `.github/workflows/ci.yml`.
- **managed-block:** Content injected into pre-existing (or shared) files via markers. `/clear` removes only the marked block. `.claude/settings.local.json` (treated as managed-block for forward safety even though it didn't pre-exist).

## Validation Hierarchy

Layers applicable to this project (skill repo, no deployment):

1. **Layer 1 — Static checks:** Python syntax; JSON schemas parse; markdown frontmatter intact.
2. **Layer 2 — Unit tests:** `python -m unittest discover skills/development-harness/scripts/tests`. Required for code-bearing units.
3. **Layer 3 — Integration tests:** New integration tests under `scripts/tests/integration/` for worktree dispatch / merge.
4. **Layer 4 — E2E tests:** Not configured. Self-test phase (PHASE_013) serves the equivalent role.
5. **Layer 5 — CI checks:** `.github/workflows/ci.yml` runs Layer 2 on PR/push.
6. **Layer 6 — Deployed smoke checks:** Not applicable (no deployment).
7. **Layer 7 — Deployed E2E:** Not applicable.

## Loop Mechanics

The invoke loop is gated by a session flag. `/invoke-development-harness` creates `.harness/.invoke-active` as its first step. The stop hook checks for this flag before any other logic — absent flag means the hook is a no-op (protects non-harness sessions in the same workspace).

Authority chain (Claude Code hook protocol):

1. Check `.harness/.invoke-active` exists.
2. Respect Claude Code's built-in `stop_hook_active` loop guard.
3. Read `state.json` for loop budget, blockers, open questions.
4. Run `select_next_unit.py`.
5. Compare selector output with `checkpoint.next_action` substring match.
6. **Continue** (exit 2, `decision: block`) if all pass.
7. **Stop** (exit 0, delete `.invoke-active`) otherwise.

## Git Integration

- Default branch: `main`.
- Branch convention: `<type>/<short-description>` (e.g., `feat/phase-001-schema`).
- Commit convention: conventional-commits (e.g., `feat(harness): extend phase-graph schema with depends_on`).
- Merge strategy: squash.
- Review policy: AI review via the installed `code-review` skill. The harness invokes `code-review` during phase completion review (Step 9).

Every completed unit results in a commit. When the `commit-agent-changes` skill is installed (it is, under `skills/`), the harness delegates commit/PR creation to it.

## Deployment Truth

This repo does not deploy. All phases are non-deploy-affecting. Deployment truth gates never fire.

## Skills Discovery

At the start of each invoke, the harness checks for:

- `commit-agent-changes` (under `skills/`): used during Step 11 (commit/PR).
- `code-review` (under `skills/`): used during Step 9 (phase completion review).

Both are present in this repo.

## Installed Tool

- **Tool:** Claude Code.
- **Commands dir:** `.claude/commands/`.
- **Rules dir:** `.claude/rules/`.
- **Hook config:** `.claude/settings.local.json` (managed-block for the Stop hook entry).

## Key Principle

The harness builds a task-closing machine, not a project-finishing fantasy. Every unit of work has a validator. Every completed unit has evidence. Every phase completion passes an internal review. The dogfood nature requires extra discipline around the frozen/canonical split — every agent session must remember that edits go to `skills/**`, not `.harness/scripts/**`.
