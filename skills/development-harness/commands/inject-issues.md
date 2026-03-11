# Command: Inject Issues

**Mode:** Analysis + structured update

## Prerequisites

- `.harness/` directory exists in the workspace
- `.harness/ARCHITECTURE.md` exists
- `.harness/phase-graph.json` exists
- `.harness/state.json` exists

## Procedure

### Step 1 — Load context

Read `.harness/ARCHITECTURE.md` to understand the current project structure, phases, and data-authority rules.

### Step 2 — Accept issue descriptions

Accept freeform issue descriptions from the user. Supported input forms:
- **Inline text** — user types issues directly in the chat
- **File path** — user provides a path to a text file containing issues
- **Conversational list** — user describes issues across multiple messages; collect them all before proceeding

If the user hasn't provided issues yet, ask for them now.

### Step 3 — Normalize issues

Run `normalize_issues.py` to parse the raw text into structured JSON records.

**With inline text:**
```
python3 .harness/scripts/normalize_issues.py --text "USER_TEXT" --output-dir .harness/issues/
```

**With a file:**
```
python3 .harness/scripts/normalize_issues.py --input PATH --output-dir .harness/issues/
```

The script auto-detects the next `ISSUE_NNN` number from existing files in the output directory. Review the JSON output it prints to confirm the issues were parsed correctly.

### Step 4 — Refine each issue

For each normalized issue, review and fill in missing fields. Ask the user when information is not obvious from context:

- **severity** — `critical` | `high` | `medium` | `low` (default is `medium`; escalate if blocking or data-loss)
- **expected_behavior** — what should happen
- **observed_behavior** — what actually happens
- **reproduction_steps** — ordered steps to trigger the issue
- **suspected_phase** — which phase in `phase-graph.json` is affected
- **suspected_units** — which unit(s) within that phase are related
- **deployment_impact** — does this affect deployed environments?

### Step 5 — Update issue files

Write the refined information back to each `ISSUE_NNN.json` file in `.harness/issues/`.

### Step 6 — Map issues to phases

For each issue, determine which phase in `phase-graph.json` it affects:

1. Read `phase-graph.json`
2. Match `suspected_phase` to existing phases
3. For each affected phase, either:
   - Add bug-fix units to the existing phase document (`PHASE_XXX_slug.md`), **or**
   - Create a new `PHASE_XXX_bugfixes.md` if the fixes don't fit an existing phase
4. Each bug-fix unit must have:
   - `id` — e.g. `bugfix_ISSUE_004`
   - `description` — what the fix does
   - `acceptance_criteria` — the bug is fixed **and** a regression test passes
   - `validation_method` — how to verify (test command, manual check, etc.)

### Step 7 — Reprioritize phase-graph.json

Adjust priority based on severity:

| Severity | Action |
|----------|--------|
| **Critical** (blocks current work) | Add as blocker in `state.json`; insert fix unit immediately before current work |
| **High** (affects upcoming phases) | Insert fix units before remaining work in affected phases |
| **Medium / Low** | Append fix units to the end of relevant phases |

Update `phase-graph.json` with the new units and any reordering.

### Step 8 — Generate failing test stubs

Where possible, generate failing test stubs that reproduce the reported issue:

- Place tests in the project's existing test directory structure
- Each stub should fail with a clear message referencing the issue ID
- These serve as regression checks — they pass once the fix is applied

If the issue is too vague for a test stub, note this and skip.

### Step 9 — Update state.json

Update the issue counters in `state.json`:
- `issues.total` — increment by number of new issues
- `issues.open` — increment by number of new issues
- `issues.resolved` — unchanged

If any critical issues were added as blockers, update the `blockers` array.

### Step 10 — Update checkpoint.md

Add an entry to `checkpoint.md` noting:
- How many issues were ingested
- Which phases are affected
- Whether priority changed
- Whether blockers were added

### Step 11 — Report

Output a summary to the user:

- **Issues ingested:** count and IDs
- **Phase impact:** which phases gained bug-fix units
- **Priority changes:** any reordering applied to `phase-graph.json`
- **Blockers added:** any critical issues now blocking work
- **Test stubs generated:** list of test files created (or "none")
