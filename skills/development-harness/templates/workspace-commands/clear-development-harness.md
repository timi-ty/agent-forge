---
description: Remove all development harness artifacts safely using the manifest
---

# Clear Development Harness

1. Read `.harness/manifest.json`.
2. If the manifest is missing or corrupt, **refuse to proceed**. Tell the user the manifest is required for safe clearing and stop.
3. Run dry-run: `python3 .harness/scripts/clear_harness.py`
4. Present the report to the user:
   - **Will delete** (harness-owned): each file/directory
   - **Will remove managed blocks** from: each file
   - **Will preserve** (product-owned): each file with note
   - **Warnings**: any edge cases
5. Ask for confirmation using AskQuestion:
   - "Yes, clear the harness"
   - "No, cancel"
   - "Exclude specific items" (if chosen, ask which items to keep and re-run dry-run)
6. On confirmation: `python3 .harness/scripts/clear_harness.py --execute --force`
7. Run `git status` so the user can review the workspace.
8. Report: what was deleted, managed blocks removed, files preserved, any errors.

## Safety

- Never delete without a valid manifest
- Never touch product-owned files
- Never delete when ownership is ambiguous — ask instead
