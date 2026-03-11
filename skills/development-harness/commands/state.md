# Command: State

Read-only harness state report with alignment analysis.

## Mode

Read-only analysis. No modifications to any files.

## Steps

### 1. Validate Structural Health

Run `validate_harness.py` from `.harness/scripts/`:

```
python3 .harness/scripts/validate_harness.py
```

If validation fails, report errors prominently and continue with whatever data is readable.

### 2. Read Harness Data

Read all of these files:

- `.harness/state.json`
- `.harness/phase-graph.json`
- `.harness/config.json`
- `.harness/checkpoint.md`
- `.harness/ARCHITECTURE.md`
- All files in `PHASES/` directory

### 3. Quick Checks (Optional)

Run these if the project supports them. Skip silently if not configured.

- `git status` — working tree cleanliness
- Test runner from `config.json` → `testing` section (e.g., `pnpm test`, `pytest`)
- Deployment smoke test from `config.json` → `deployment.smoke_test_url` (HTTP GET, check for 200)

Record which checks were run, which were skipped, and why.

### 4. Compute Alignment Metrics

Derive each metric from harness data. Show the calculation, not just the number.

| Metric | Derivation |
|--------|-----------|
| **Roadmap coverage** | Count ROADMAP.md sections that have a corresponding phase in `phase-graph.json`. Report as `N / M sections covered`. |
| **Phase coverage** | Phases with status `completed` / total phases. |
| **Unit coverage** | Units with status `completed` / total units across all phases. |
| **Test coverage** | Completed units that have non-empty `validation_evidence` / total completed units. |
| **Deploy coverage** | Deploy-verified phases (with Layer 6+ evidence) / total deploy-affecting phases. If no deploy-affecting phases exist, report N/A. |

### 5. Check Staleness

- Age of `state.json` — compare `last_updated` timestamp against current time
- Last sync — compare `drift.last_sync` against current time
- Checkpoint currency — compare `checkpoint.timestamp` against `state.json` `last_updated`

Flag anything older than 24 hours as potentially stale.

### 6. Output Report

Use this exact format:

```
# Harness State Report

## App State
(what exists in code, what works, what is broken — cite file paths and test output)

## Harness State
(active phase, progress, issue counts, last sync time)

## Alignment
(each metric with how it was derived)

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

- Never pretend sync has happened if `drift.last_sync` has no value or is stale.
- Clearly separate known facts (direct data reads, test output) from inference (keyword matches, heuristic coverage).
- If percentages are reported, show the numerator and denominator (e.g., "3 / 7 units completed (43%)").
- If a quick check was skipped, say so. Do not fabricate results.
- If `state.json` or `phase-graph.json` is missing or corrupt, report the structural failure rather than guessing state.
