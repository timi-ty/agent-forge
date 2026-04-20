---
description: "Modify harness configuration or structure (plan mode)"
---

# Update Development Harness

You are modifying the development harness itself. Use Plan Mode — research, plan, get approval, then execute.

## Step 0: Resolve tool paths

Read `.harness/config.json` and check the `tool` field. Set `$HOOKS_DIR` to `.cursor/hooks` (cursor) or `.claude/hooks` (claude-code).

## Step 0.5: Schema Version Precheck

Before anything else, detect Python and run `validate_harness.py` to confirm the installed `.harness/` matches the skill's schema version:

```bash
PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
[ -z "$PY" ] && { echo "Error: Python 3 is required but neither python3 nor python was found"; exit 1; }
$PY .harness/scripts/validate_harness.py
```

- **Exit 0** — schema matches; continue.
- **Exit 1 with `/create-development-harness` in the error output** — the harness on disk is on an older schema than the skill. **Stop here.** Surface the validator's errors verbatim and tell the user:
  > "The harness on disk is on an older schema than the installed skill. Re-run `/create-development-harness` to regenerate `.harness/` artifacts at the current schema version. `ROADMAP.md` and `PHASES/*.md` are preserved by the recreate flow. See `SKILL.md` § 'Version upgrades' — **no migration script is provided by design**."

  Do NOT attempt in-place migration. Do NOT enter Plan Mode. This command does not own schema migration; `/create-development-harness` is the only supported upgrade path.
- **Exit 1 without the `/create-development-harness` pointer** — a different structural problem. Report the errors and stop.

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
   - Hook changes (add/modify/remove `$HOOKS_DIR/` files)

   > `schema_version` bumps are NOT a category — they are rejected by the Step 0.5 precheck above and redirected to `/create-development-harness`.
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

## Schema Migration (not supported)

`/update-development-harness` does NOT perform schema-version migrations. Schema mismatches are detected and rejected by Step 0.5 above. The only supported upgrade path is re-running `/create-development-harness` — it preserves `ROADMAP.md` and `PHASES/*.md` while regenerating the rest of `.harness/`. **No migration script is provided by design** (see `SKILL.md` § 'Version upgrades' for the cost rationale).

## Guardrails

- Never modify product-owned files without explicit user approval.
- Never execute without a saved plan and user approval.
- Always validate after changes.
- Warn if the update would invalidate current execution state (e.g., removing the active phase).
