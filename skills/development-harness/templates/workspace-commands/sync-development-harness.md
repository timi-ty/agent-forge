---
description: "Sync harness state with code reality"
---

# Sync Development Harness

You are reconciling the development harness with the actual state of the codebase. Be conservative — only update statuses when evidence supports it.

## Procedure

1. Read `.harness/ARCHITECTURE.md` for data authority rules.
2. Run: `python3 .harness/scripts/validate_harness.py`
   - Fix structural issues if possible. If unfixable, report and stop.
3. Gather workspace ground truth:
   - File tree (exclude `.harness/`, `.git/`, `node_modules/`, `dist/`, `build/`)
   - Test files (`*test*`, `*spec*` patterns)
   - CI config (`.github/workflows/`)
   - Deployment config (`vercel.json`, `Dockerfile`, etc.)
   - `git log --oneline -20`
4. Run: `python3 .harness/scripts/sync_harness.py`
   - Review output. It uses `present-but-unverified` for anything without evidence. Follow the same rule.
5. For each phase in `.harness/phase-graph.json`:
   - Read `PHASES/PHASE_XXX_slug.md`
   - Compare claimed unit statuses against evidence (test output, build, CI, deploy signals)
   - **Never upgrade a unit to `completed` just because files exist**
6. Update `.harness/phase-graph.json` unit statuses only with evidence:
   - Test pass → may mark `completed`
   - Files exist, no tests → `present-but-unverified` (note only, status unchanged)
   - No files → leave `pending` or flag regression
7. Update `.harness/state.json`:
   - Set `drift.last_sync` to current ISO timestamp
   - Record divergences in `drift.divergences`
   - Update `execution` pointers if needed
8. If phase documents need updates, apply conservatively — add info, never remove intent.
9. Update `.harness/checkpoint.md` with post-sync state.
10. Output sync report:

```
# Sync Report

## Structural Validation
(validate_harness.py results)

## Drift Detection
(sync_harness.py summary)

## Phase-by-Phase Status
(claimed vs evidence-based status, changes made)

## Changes Applied
(files modified and what changed)

## Unresolved Divergences
(recorded for human review)
```

## Evidence-Only Rule

Do not upgrade status based on file presence alone. When uncertain, record the divergence rather than forcing alignment. Never silently rewrite product intent.

## Guardrails

- Check `.harness/manifest.json` — never modify product-owned files.
- If a phase no longer matches ROADMAP, flag for human review rather than auto-correcting.
