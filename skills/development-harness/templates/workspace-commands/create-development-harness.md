# Create / Reinitialize Development Harness

Read `.harness/ARCHITECTURE.md` before doing anything.

## Context

Read these files to understand current harness state:
- `.harness/config.json` -- current configuration
- `.harness/manifest.json` -- file inventory and ownership classes
- `.harness/state.json` -- execution state
- `.harness/phase-graph.json` -- phase/unit dependency graph

## Purpose

This command rebuilds or reinitializes the development harness. Use it when:
- The harness needs to be recreated from scratch
- Configuration has changed significantly
- The ROADMAP.md has been rewritten
- Phase structure needs a full recompile

## Workflow

### 1. Assess current state

- Check which harness artifacts already exist
- Identify what the user wants to change vs. keep
- Ask the user: "What should change compared to the current harness?"

### 2. Preserve product-owned artifacts

Read `.harness/manifest.json` and identify all `product-owned` entries.
These files are NEVER deleted or overwritten:
- CI/CD workflows (`.github/workflows/`)
- E2E tests
- Application source code
- `ROADMAP.md`

### 3. Re-run creation process

Switch to Plan Mode. Save plan to `.harness/plans/`.

1. Re-inspect the repo for any changes since last creation
2. Re-read `ROADMAP.md` for updated product intent
3. Run the roadmap compiler:
   ```
   python3 .harness/scripts/compile_roadmap.py --roadmap ROADMAP.md --output .harness/phase-graph.json
   ```
4. Interrogate the skeleton: refine phase boundaries, add units with validators, set dependencies
5. Regenerate phase documents in `PHASES/`
6. Regenerate `.harness/config.json` with any updated answers
7. Regenerate `.harness/state.json` with fresh execution state
8. Regenerate `.harness/checkpoint.md`
9. Regenerate `.harness/ARCHITECTURE.md`
10. Update `.harness/manifest.json` to reflect all current files

### 4. Update workspace artifacts

- Regenerate `$COMMANDS_DIR/` workspace commands if needed
- Regenerate `$RULES_DIR/harness-*$RULE_EXT` if config changed
- Merge `$HOOK_CONFIG` stop hook (do not overwrite other hooks)

### 5. Validate

```
python3 .harness/scripts/validate_harness.py --root .
```

Fix any errors. Re-run until validation passes.

### 6. Report

Output summary: what changed, active phase, first unit, next steps.
Tell the user to run `/invoke-development-harness` to begin.
