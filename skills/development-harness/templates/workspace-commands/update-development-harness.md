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
2. Detect Python:
   ```bash
   PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
   [ -z "$PY" ] && { echo "Error: Python 3 is required but neither python3 nor python was found"; exit 1; }
   ```
3. Ask the user what they want to change. Do not guess. Wait for their answer.
4. Categorize the change:
   - Phase restructuring (add/remove/reorder phases)
   - Configuration (git policy, deployment, testing, stack)
   - Validation policy (required layers, quality gates)
   - Loop behavior (budget, stop conditions, hooks)
   - Schema migration (v1 handles same-version only)
   - Hook changes (add/modify/remove `$HOOKS_DIR/` files)
5. Check `.harness/manifest.json` for ownership of all affected files.
   - Harness-owned → proceed.
   - Product-owned → explain, list files, get explicit approval.
6. Save plan to `.harness/plans/update-YYYY-MM-DD-short-description.md`:
   - What changes, which files, ownership status, rollback strategy, impact on execution.
   - Present to user and wait for approval.
7. After approval, execute the changes.
8. Update `.harness/manifest.json` if ownership changed (new/removed/reclassified files).
9. Run: `$PY .harness/scripts/validate_harness.py`
   - Fix any failures before continuing.
10. Update `.harness/state.json` (timestamp, execution pointers) and `.harness/checkpoint.md`.

## Schema Migration

If `schema_version` changes: read old schema, transform, write with new version. v1 implements the trivial case only (no transformation). For non-trivial migrations, explain limitations and suggest manual steps.

## Guardrails

- Never modify product-owned files without explicit user approval.
- Never execute without a saved plan and user approval.
- Always validate after changes.
- Warn if the update would invalidate current execution state (e.g., removing the active phase).
