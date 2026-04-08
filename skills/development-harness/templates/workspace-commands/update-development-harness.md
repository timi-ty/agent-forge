---
description: "Modify harness configuration or structure (plan mode)"
---

# Update Development Harness

You are modifying the development harness itself. Use Plan Mode — research, plan, get approval, then execute.

## Step 0: Resolve tool paths

Read `.harness/config.json` and check the `tool` field. Set `$HOOKS_DIR` to `.cursor/hooks` (cursor) or `.claude/hooks` (claude-code).

## Procedure

1. Read all harness files:
   - `.harness/ARCHITECTURE.md`, `config.json`, `state.json`, `phase-graph.json`, `manifest.json`, `checkpoint.md`
   - All `PHASES/*.md` files
2. Ask the user what they want to change. Do not guess. Wait for their answer.
3. Categorize the change:
   - Phase restructuring (add/remove/reorder phases)
   - Configuration (git policy, deployment, testing, stack)
   - Validation policy (required layers, quality gates)
   - Loop behavior (budget, stop conditions, hooks)
   - Schema migration (v1 handles same-version only)
   - Hook changes (add/modify/remove `$HOOKS_DIR/` files)
4. Check `.harness/manifest.json` for ownership of all affected files.
   - Harness-owned → proceed.
   - Product-owned → explain, list files, get explicit approval.
5. Save plan to `.harness/plans/update-YYYY-MM-DD-short-description.md`:
   - What changes, which files, ownership status, rollback strategy, impact on execution.
   - Present to user and wait for approval.
6. After approval, execute the changes.
7. Update `.harness/manifest.json` if ownership changed (new/removed/reclassified files).
8. Run: `$PY .harness/scripts/validate_harness.py`
   - Fix any failures before continuing.
9. Update `.harness/state.json` (timestamp, execution pointers) and `.harness/checkpoint.md`.

## Schema Migration

If `schema_version` changes: read old schema, transform, write with new version. v1 implements the trivial case only (no transformation). For non-trivial migrations, explain limitations and suggest manual steps.

## Guardrails

- Never modify product-owned files without explicit user approval.
- Never execute without a saved plan and user approval.
- Always validate after changes.
- Warn if the update would invalidate current execution state (e.g., removing the active phase).
