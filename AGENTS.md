# AGENTS.md

This repo (`agent-forge`) is a skill distribution repo. It is also the workspace where the `development-harness` skill is being upgraded to a multi-agent parallel execution model — **dogfood**. This document orients any agent working here.

## Start here

1. Read [`.harness/ARCHITECTURE.md`](.harness/ARCHITECTURE.md) for the harness control-plane layout, data authority, and loop mechanics.
2. Read [`ROADMAP.md`](ROADMAP.md) for product intent (the 13-phase multi-agent upgrade plan).
3. Read the active phase doc under [`PHASES/`](PHASES/) — currently [`PHASE_001_schema-and-data-model.md`](PHASES/PHASE_001_schema-and-data-model.md).

## Running the harness

Run one of the workspace slash commands:

| Command | Purpose |
|---|---|
| `/create-development-harness` | Rebuild or reinitialize the harness |
| `/invoke-development-harness` | Execute the next unit of work |
| `/update-development-harness` | Modify harness configuration or the phase plan |
| `/harness-state` | Report current harness and project state |
| `/sync-development-harness` | Sync the harness with code reality |
| `/clear-development-harness` | Remove all harness artifacts |
| `/inject-harness-issues` | Report problems or inject issues into the tracker |

## Key rules

- **Edit target:** every skill edit under the roadmap lands in `skills/development-harness/**`. The scripts in `.harness/scripts/` are a **frozen copy** made at bootstrap time; do not edit them.
- **Authority:** `.harness/phase-graph.json` via `select_next_unit.py` is the canonical source for "what to do next". `state.json` is a runtime snapshot, `checkpoint.md` is a human-readable summary.
- **Git:** feature branch per unit, conventional-commits, squash-merge, AI review via the installed `code-review` skill during phase completion. Never merge a PR without explicit user approval.
- **Validation:** every completed unit must carry specific evidence in `phase-graph.json` (exact command + exit code, not "tests pass").
- **Deployment:** this repo does not deploy. Deployment truth gates never fire.

## Skills available in this workspace

Under `skills/`:

- `commit-agent-changes` — delegated to during Step 11 (commit + PR)
- `code-review` — delegated to during Step 9 (phase completion review)
- `development-harness` — the skill being upgraded (canonical source for all roadmap edits)
- Others: `aws`, `btw`, `clickup`, `create-issue`, `figma`, `issue-resolution-report`, `playwright-pool`, `redeploy-frontend`, `sync-skills`

## CI

`.github/workflows/ci.yml` runs `python -m unittest discover skills/development-harness/scripts/tests` on PR and push to `main`.

## Dogfood caveat

The harness you are running is a version-frozen copy of the skill you are editing. Early-phase bugs in schema or validator land in `skills/**` and only take effect when the harness is re-bootstrapped (`/clear` + `/create`). This split is intentional — it keeps the harness stable mid-upgrade.
