---
description: Inject issues into the development harness — normalizes descriptions, maps to phases, reprioritizes work
---

# Inject Issues

1. Read `.harness/ARCHITECTURE.md` for project context.
2. Accept issue descriptions from the user (inline text, file path, or conversational list). If none provided yet, ask now.
3. Detect Python:
   ```bash
   PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
   [ -z "$PY" ] && { echo "Error: Python 3 is required but neither python3 nor python was found"; exit 1; }
   ```
4. Run the normalizer:
   - Inline: `$PY .harness/scripts/normalize_issues.py --text "USER_TEXT" --output-dir .harness/issues/`
   - File: `$PY .harness/scripts/normalize_issues.py --input PATH --output-dir .harness/issues/`
5. For each normalized issue, refine missing fields (ask the user when unclear):
   - severity (`critical` | `high` | `medium` | `low`)
   - expected vs. observed behavior
   - reproduction steps
   - suspected phase and units
   - deployment impact
6. Write refined data back to each `ISSUE_NNN.json` in `.harness/issues/`.
7. Read `phase-graph.json`. For each issue:
   - Match to the affected phase
   - Add bug-fix units (id, description, acceptance criteria, validation method) to the phase doc or create `PHASE_XXX_bugfixes.md`
8. Reprioritize `phase-graph.json`:
   - Critical → blocker in `state.json`, fix before current work
   - High → fix before remaining work in affected phase
   - Medium/Low → append fix units to phase
9. Generate failing test stubs where reproduction is clear enough.
10. Update `state.json` issue counters (`total`, `open`, `resolved`) and blockers.
11. Update `checkpoint.md` with issue impact.
12. Report to user: issues ingested (count + IDs), phase impact, priority changes, blockers added, test stubs generated.
