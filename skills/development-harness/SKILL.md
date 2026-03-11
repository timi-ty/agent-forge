---
name: development-harness
description: A project-local development harness that compiles a ROADMAP.md into phased, validator-backed autonomous execution. Commands - create, invoke, update, state, sync, clear, inject-issues. Use when the user says 'create development harness', 'create dev harness', 'invoke harness', 'continue from harness', 'harness state', 'sync harness', 'update harness', 'clear harness', 'inject issues', or similar.
---

# Development Harness

A project-local control plane that compiles product intent (ROADMAP.md) into a dependency-ordered set of validator-backed phase contracts, then executes them one bounded unit at a time.

## How It Works

1. The user runs "create development harness" to bootstrap the harness in a workspace
2. The harness asks questions, reads ROADMAP.md, and generates all artifacts
3. After creation, 7 workspace slash commands are available in `.cursor/commands/`
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

## Key Principle

The harness builds a task-closing machine, not a project-finishing fantasy. Every unit of work must have a validator. Every completed unit must have evidence. Every phase completion must pass an internal review checklist. Deployment truth gates block deploy-affecting phases until verification passes.
