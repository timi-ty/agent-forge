---
name: development-harness
description: A project-local development harness that compiles a ROADMAP.md into phased, validator-backed autonomous execution. Commands - create, invoke, update, state, sync, clear, inject-issues. Use when the user says 'create development harness', 'create dev harness', 'invoke harness', 'continue from harness', 'harness state', 'sync harness', 'update harness', 'clear harness', 'inject issues', or similar.
---

# Development Harness

A project-local control plane that compiles product intent (ROADMAP.md) into a dependency-ordered set of validator-backed phase contracts, then executes them one bounded unit at a time. Works with both Cursor and Claude Code.

## How It Works

1. The user runs "create development harness" to bootstrap the harness in a workspace
2. The harness detects the host tool (Cursor or Claude Code) and generates tool-appropriate artifacts
3. After creation, 7 workspace slash commands are available in the tool's commands directory
4. The user runs `/invoke-development-harness` to execute work
5. A stop hook keeps the agent iterating until a verifiable goal is reached or ambiguity is encountered
6. Between sessions, the user can check state, sync, inject issues, or update the harness

## Command Routing

Based on the user's request, read the corresponding command file from this skill's `commands/` directory:

| User Intent | Command File |
|---|---|
| Create / initialize the harness | `commands/create.md` |
| Continue work / invoke / run harness | `commands/invoke.md` |
| Modify the harness itself | `commands/update.md` |
| Report harness and app state | `commands/state.md` |
| Sync harness with code reality | `commands/sync.md` |
| Remove all harness artifacts | `commands/clear.md` |
| Report problems / inject issues | `commands/inject-issues.md` |

**Important:** After reading the command file, follow its instructions completely. Each command file is self-contained.

## Architecture Summary

- **state.json** is a runtime snapshot only -- pointers and summaries
- **phase-graph.json** is the canonical source of truth for phase/unit status
- **select_next_unit.py** is the authoritative "what to do next" source
- **checkpoint.md** is a human-readable summary -- never treat as authoritative data
- **manifest.json** tracks three ownership classes: harness-owned, product-owned, managed-block

For full architecture details, see `references/architecture.md`.

## Python Detection

All harness scripts require Python 3. Before running any harness script, detect the available Python command:

```bash
PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
[ -z "$PY" ] && { echo "Error: Python 3 is required but neither python3 nor python was found"; exit 1; }
```

All command files use `$PY` to invoke Python scripts. Run this detection once per shell session before calling any harness command.

## Version upgrades

When the skill's `schema_version` bumps (e.g., v1 → v2), existing harnesses become incompatible and `validate_harness.py` rejects them with a pointer to re-create. The upgrade path is:

1. **Re-run `/create-development-harness`** to regenerate `.harness/` artifacts at the new schema version.
2. **`ROADMAP.md` and `PHASES/*.md` are preserved** — the recreate flow reads them and rebuilds the harness around them. Product intent (ROADMAP) and phase contracts (PHASES) never get regenerated from scratch.
3. Harness-owned files that do get regenerated: `state.json`, `phase-graph.json`, `checkpoint.md`, `manifest.json`, the scripts under `.harness/scripts/`, the workspace commands, and the hook/rule files.

**No migration script is provided by design.** The cost of a reliable general-purpose migration (covering every schema-version delta across every downstream file) exceeds the cost of regenerating with `ROADMAP.md` + `PHASES/*.md` as the preserved inputs. `config.execution_mode.versioning.break_on_schema_bump: true` (the default, set during Phase 2 of `/create-development-harness`) enforces this — if a user prefers in-place migration attempts they can opt into `break_on_schema_bump: false`, but the harness ships no migration tooling to back that choice up.

## Key Principle

The harness builds a task-closing machine, not a project-finishing fantasy. Every unit of work must have a validator. Every completed unit must have evidence. Every phase completion must pass an internal review checklist. Deployment truth gates block deploy-affecting phases until verification passes.
