# Command: Sync

Conservative reconciliation of harness state with code reality.

## Mode

Analysis + conservative update. Writes only to harness-owned files. Never modifies product-owned files.

## Steps

### 1. Read Architecture

Read `.harness/ARCHITECTURE.md` to confirm file layout and data authority rules.

### 2. Validate Structure

Run `validate_harness.py`:

```
$PY .harness/scripts/validate_harness.py
```

If critical errors exist, fix structural issues before proceeding. If unfixable, report and stop.

### 3. Inspect Actual Code

Gather ground truth about the workspace:

- File tree (excluding `.harness/`, `.git/`, `node_modules/`, `dist/`, `build/`, `__pycache__/`)
- Test files (files matching `*test*`, `*spec*` patterns)
- CI config (`.github/workflows/`, `ci.yml`, etc.)
- Deployment config (`vercel.json`, `Dockerfile`, etc.)
- Recent git log: `git log --oneline -20`

### 4. Run Automated Drift Detection

```
$PY .harness/scripts/sync_harness.py
```

Review its output carefully. Remember its evidence-only claiming rule: the script uses `present-but-unverified` and `unknown` for anything without test/build/CI evidence. Follow the same discipline.

### 5. Phase-by-Phase Comparison

For each phase in `phase-graph.json`:

1. Read the corresponding `PHASES/PHASE_XXX_slug.md` document
2. Compare what exists in code against what the phase document describes
3. Check each unit's claimed status against actual evidence:
   - Does the code exist? (file presence)
   - Do tests exist? (test file presence)
   - Do tests pass? (test output evidence)
   - Does CI pass? (CI signal)
   - Is it deployed? (deployment evidence)

### 6. Update Phase Graph (Evidence-Only)

Update `phase-graph.json` unit statuses ONLY when there is concrete evidence:

| Evidence Type | Allowed Status Transition |
|---------------|--------------------------|
| Test output showing pass | `pending` → `completed`, `in_progress` → `completed` |
| Build output showing success | `pending` → `in_progress` |
| CI green signal | Confirms existing `completed` status |
| Files exist but no test evidence | Mark as `present-but-unverified` in notes, do NOT upgrade to `completed` |
| No files found | Leave as `pending` or flag regression |

**Never upgrade a unit to `completed` just because relevant files exist.**

### 7. Update State

Update `state.json`:

- Set `drift.last_sync` to current ISO timestamp
- Record any divergences in `drift.divergences`
- Update `execution` pointers if phase graph changes affected them
- Update `validation_summary` and `deployment_summary` if new evidence was gathered

### 8. Update Phase Documents (Conservative)

If phase documents need updates (new gaps found, completed work not reflected):

- Propose specific changes before applying
- Apply conservatively — add information, never remove intent
- **Never silently rewrite product intent**

### 9. Update Checkpoint

Update `checkpoint.md` to reflect post-sync state.

### 10. Output Sync Report

```
# Sync Report

## Structural Validation
(validate_harness.py output)

## Drift Detection
(sync_harness.py output summary)

## Phase-by-Phase Status
(for each phase: claimed status vs evidence-based status, changes made)

## Changes Applied
(list every file modified and what changed)

## Unresolved Divergences
(things that could not be reconciled — recorded for human review)

## Staleness After Sync
(updated timestamps, remaining stale areas)
```

## Evidence-Only Rule

`sync_harness.py` uses `present-but-unverified` and `unknown` for anything without test/build/CI evidence. The agent must follow the same discipline:

- Do not upgrade status based on file presence alone.
- When uncertain, record the divergence rather than forcing alignment.
- If a unit appears complete in code but has no test evidence, mark it `present-but-unverified` in the divergence log rather than `completed` in the phase graph.

## Guardrails

- Never modify product-owned files (check `manifest.json` ownership).
- Never silently rewrite product intent in phase documents.
- If sync reveals a phase that no longer matches the ROADMAP, record the divergence and flag for human review rather than auto-correcting.
