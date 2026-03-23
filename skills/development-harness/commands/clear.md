# Command: Clear Harness

**Mode:** Destructive action with mandatory confirmation

## Safety Rules

- **NEVER** delete without a valid `manifest.json`
- **NEVER** touch product-owned files
- **NEVER** delete when ownership is ambiguous — ask the user instead
- The clear script handles managed-block removal (strips only `HARNESS:START` / `HARNESS:END` blocks from files)
- Product-owned files scaffolded by the harness (CI/CD configs, E2E setup) are explicitly preserved

## Procedure

### Step 1 — Load manifest

Read `.harness/manifest.json`.

### Step 2 — Validate manifest

If `manifest.json` does not exist or cannot be parsed as valid JSON:
- **REFUSE to proceed.**
- Tell the user: *"The manifest is required for safe clearing. Without it, the harness cannot determine which files it owns. Do not attempt manual cleanup."*
- Stop here. Do not fall back to heuristics or manual file discovery.

### Step 3 — Dry-run

Run `clear_harness.py` in dry-run mode (no `--execute` flag):

```
python3 .harness/scripts/clear_harness.py
```

This prints a JSON report of what will happen. Parse the report.

### Step 4 — Present the report

Show the dry-run results to the user in a readable format:

- **Will delete** (harness-owned): list each file and directory
- **Will remove managed blocks** from: list each file, note whether a block was found
- **Will preserve** (product-owned): list each file with its note
- **Warnings**: any edge cases (missing files, unknown ownership, etc.)

### Step 5 — Ask for confirmation

Ask the user with these options:

1. **"Yes, clear the harness"** — proceed with deletion
2. **"No, cancel"** — abort immediately
3. **"Exclude specific items"** — if selected, ask the user which items to keep, then re-run dry-run excluding those items

Do not proceed without explicit user confirmation.

### Step 6 — Execute

On confirmation, run `clear_harness.py` with execute and force flags:

```
python3 .harness/scripts/clear_harness.py --execute --force
```

### Step 7 — Show git status

Run `git status` so the user can see the resulting workspace state.

### Step 8 — Report

Tell the user:
- What was deleted (count and paths)
- What managed blocks were removed (count and files)
- What was preserved (product-owned files)
- Any errors that occurred during deletion
