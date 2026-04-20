# Command: Update

Plan-mode modification of harness configuration and structure.

## Mode

Plan Mode. Research first, ask the user what they want, draft a plan, save it, execute only after approval.

## Steps

### 0. Schema Version Precheck

Before anything else, run `validate_harness.py` to confirm the installed `.harness/` matches the installed skill's schema version:

```
$PY .harness/scripts/validate_harness.py
```

- **Exit 0 (valid)** — continue to Step 1.
- **Exit 1 (invalid) with `/create-development-harness` in the error output** — the harness is on an older schema than the skill. **Stop here.** Surface the validator's error messages verbatim and tell the user:
  > "The harness on disk is on an older schema than the installed skill. Re-run `/create-development-harness` to regenerate `.harness/` artifacts at the current schema version. `ROADMAP.md` and `PHASES/*.md` are preserved by the recreate flow. See `SKILL.md` § 'Version upgrades' for the full policy — **no migration script is provided by design**."

  Do NOT attempt in-place migration. Do NOT enter Plan Mode. The `/update-development-harness` command does not own schema migration; `/create-development-harness` is the only supported upgrade path.
- **Exit 1 (invalid) without the `/create-development-harness` pointer** — a different structural problem (malformed JSON, missing required keys). Report the errors and stop.

### 1. Read All Harness Files

Read these to understand current state:

- `.harness/ARCHITECTURE.md`
- `.harness/config.json`
- `.harness/state.json`
- `.harness/phase-graph.json`
- `.harness/manifest.json`
- `.harness/checkpoint.md`
- All files in `PHASES/`

### 2. Ask the User

Ask what they want to change. Do not guess. Wait for their answer before proceeding.

### 3. Categorize the Change

Classify the requested change into one or more categories:

| Category | Examples |
|----------|---------|
| **Phase restructuring** | Add, remove, reorder, split, or merge phases |
| **Configuration change** | Git policy, deployment config, testing config, stack info |
| **Validation policy change** | Adjust which validation layers are required |
| **Loop behavior change** | Budget, stop conditions, hook parameters |
| **Hook changes** | Add, modify, or remove hooks in the tool's hooks directory |

> `schema_version` bumps are NOT a category — they are detected by Step 0 and redirected to `/create-development-harness`. See "Schema Migration (not supported)" below.

### 4. Check Ownership

Read `manifest.json` and verify all files affected by the change are harness-owned.

- If all affected files are harness-owned → proceed to planning.
- If any affected files are product-owned → explain to the user that the change touches product-owned files, list them, and get explicit approval before continuing.
- If any affected files are managed-block → note which blocks will be modified.

### 5. Save Plan

Write the plan to `.harness/plans/` with a descriptive filename:

```
.harness/plans/update-YYYY-MM-DD-short-description.md
```

The plan must include:
- What will change
- Which files will be modified
- Ownership status of each affected file
- Rollback strategy (how to undo if needed)
- Expected impact on current execution state

Present the plan to the user and wait for approval.

### 6. Execute Changes

After approval, apply the changes:

- For phase restructuring: update `phase-graph.json`, create/modify/remove `PHASES/` documents
- For configuration changes: update `config.json`
- For validation policy changes: update `config.json` quality section and relevant rule files
- For loop behavior changes: update `config.json` and hook scripts
- For hook changes: modify files in the tool's hooks directory (`.cursor/hooks/` or `.claude/hooks/`)

### 7. Update Manifest

If ownership changed (new files added, files removed, ownership class changed):

- Add new entries to `manifest.json`
- Remove entries for deleted files
- Update ownership class if it changed

### 8. Validate After Changes

Run `validate_harness.py` to confirm structural integrity:

```
$PY .harness/scripts/validate_harness.py
```

If validation fails, fix the issues before continuing.

### 9. Update State and Checkpoint

- Update `state.json` with new `last_updated` timestamp
- If phase graph changed, update `execution` pointers
- Update `checkpoint.md` to reflect the changes made

### 10. Schema Migration (not supported)

`/update-development-harness` does NOT perform schema-version migrations. Schema mismatches are detected and rejected by Step 0 above. The only supported upgrade path is re-running `/create-development-harness` — it preserves `ROADMAP.md` and `PHASES/*.md` while regenerating the rest of `.harness/`. **No migration script is provided by design** (see `SKILL.md` § 'Version upgrades' for the cost rationale).

If the user's requested change happens to need a schema bump, tell them so and redirect to `/create-development-harness`. Do not attempt to edit `schema_version` values in place.

## Guardrails

- Never modify product-owned files without explicit user approval.
- Never execute changes without saving a plan first.
- Never execute a plan without user approval.
- Always run `validate_harness.py` after changes.
- If the update would invalidate current execution state (e.g., removing the active phase), warn the user explicitly before proceeding.
