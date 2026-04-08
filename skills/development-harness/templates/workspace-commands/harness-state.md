---
description: "Report full harness state with alignment analysis"
---

# Harness State

You are reporting the state of the development harness. This is read-only — do not modify any files.

## Procedure

1. Read `.harness/ARCHITECTURE.md` for file layout context.
2. Run: `$PY .harness/scripts/validate_harness.py`
   - If it fails, report errors and continue with readable data.
3. Read these files:
   - `.harness/state.json`
   - `.harness/phase-graph.json`
   - `.harness/config.json`
   - `.harness/checkpoint.md`
   - All `PHASES/*.md` files
4. Run optional quick checks (skip silently if not configured):
   - `git status`
   - Test runner from `config.json` → `testing` (e.g., `pnpm test`)
   - HTTP GET to `config.json` → `deployment.smoke_test_url` if set
5. Compute alignment metrics from `phase-graph.json`:
   - **Phase coverage**: completed phases / total phases
   - **Unit coverage**: completed units / total units
   - **Test coverage**: completed units with `validation_evidence` / completed units
   - **Deploy coverage**: deploy-verified phases / deploy-affecting phases (N/A if none)
6. Check staleness: age of `state.json`, time since `drift.last_sync`, checkpoint currency.
7. Output this report:

```
# Harness State Report

## App State
(what exists, what works, what is broken — cite paths and output)

## Harness State
(active phase, progress, issue counts, last sync time)

## Alignment
(each metric with numerator/denominator, e.g. "3/7 units (43%)")

## Validation & Deployment Evidence
(last test run, last deploy status, CI status)

## Current Phase & Unit
(active phase, completed units, next unit)

## Blockers & Open Questions

## Risks

## Staleness
(age of state.json, time since last sync, checkpoint currency)

## Recommended Next Action
```

## Honesty Rules

- Never fabricate sync, test, or deploy results.
- Separate facts (data reads, test output) from inference.
- Show numerator and denominator for all percentages.
- If a check was skipped, say so.
