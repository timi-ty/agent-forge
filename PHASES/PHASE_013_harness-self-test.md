# PHASE_013: Harness Self-Test

## Objective
Exercise the completed upgrade end-to-end on a non-trivial fixture to surface integration issues the unit tests cannot catch. Produce a post-mortem that validates the wall-clock claim and documents any discovered papercuts.

## Why This Phase Exists
Unit and integration tests assert local correctness. The self-test answers a different question: does the whole system — create → invoke → batch → merge → checkpoint → stop-hook continuation → next batch — hold together for a real-ish roadmap with batches, a merge conflict, and a scope violation? Without this exercise, the confidence in the upgrade is theoretical.

## Scope
- Create a fixture workspace under `skills/development-harness/scripts/tests/fixtures/self-test/`:
  - 2 phases, 6 units total.
  - Designed to produce at least one batch of size ≥ 2.
  - Designed to produce at least one intentional merge conflict (two units declaring touches_paths that overlap on a literal file).
  - Designed to produce at least one intentional scope violation (a unit that edits files outside its declared touches_paths).
- Run `/create-development-harness` on the fixture; populate `touches_paths` on every unit; enable parallelism; capture the resulting phase-graph and config as part of the fixture.
- Run `/invoke-development-harness` iteratively until all phases complete. The run must exercise: ≥1 batch of size 2+, the seeded merge conflict, the seeded scope violation.
- Capture execution traces; produce a data table comparing wall-clock with parallelism on vs a sequential baseline. Verify no orphaned worktrees/branches remain.
- Write a post-mortem `skills/development-harness/scripts/tests/fixtures/self-test/POST-MORTEM.md` documenting findings. Link from `skills/development-harness/references/parallel-execution.md`.

> ⚠️ **Edit target:** `skills/development-harness/**` only. The self-test fixture is under the skill's test tree; it runs ad-hoc, not as part of CI.

## Non-goals
- Making the self-test part of regular CI — it's a release validation, not a CI gate.
- Benchmarking beyond the one fixture — real-world perf data comes from adopters.
- Fixing every papercut surfaced; follow-ups filed as issues via `/inject-harness-issues`.

## Dependencies
- PHASE_007 (invoke rewrite).
- PHASE_008 (stop-hook fleet awareness).
- PHASE_009 (safety rails).
- PHASE_010 (observability — needed to capture traces).
- PHASE_011 (docs — reader walkthrough).
- PHASE_012 (release readiness — version-mismatch UX).

## User-visible Outcomes
- Fixture exists and runs.
- Post-mortem exists under the fixture directory and is linked from `parallel-execution.md`.
- Any blocker-level issues are documented as issues via `/inject-harness-issues`.

## Units of Work

| ID | Description | Acceptance Criteria | Validation Method | Status |
|----|-------------|--------------------|--------------------|--------|
| unit_054 | Create fixture workspace with 2-phase / 6-unit mini-CRUD roadmap seeded for batch ≥2, one conflict, one scope violation | Fixture exists under `skills/development-harness/scripts/tests/fixtures/self-test/`; seeded conditions documented in a README | manual inspection | pending |
| unit_055 | Run `/create-development-harness` on the fixture; populate `touches_paths`; enable parallelism | Generated phase-graph + config committed to fixture dir for traceability | manual + grep for expected fields | pending |
| unit_056 | Run `/invoke-development-harness` iteratively; exercise batch ≥2, one conflict, one scope violation | Trace log captured; final state all-phases-complete; each seeded condition was actually exercised | trace log contents | pending |
| unit_057 | Capture traces; data table comparing wall-clock parallel vs sequential | Data table present; sequential baseline run completed for comparison; no orphaned worktrees/branches | post-mortem contains the table; `git branch --list 'harness/batch_*'` empty | pending |
| unit_058 | Write POST-MORTEM.md; link from `references/parallel-execution.md` | Post-mortem sections: setup, results, papercuts, follow-ups; link added | grep for link; manual read | pending |

## Validation Gates
- **Layer 1:** Fixture files parse (markdown, JSON).
- **Layer 2:** The seeded conditions actually fire (recorded in the trace log).
- **Layer 3:** Integration run completes end-to-end with no orphaned state.
- **Layer 4:** Post-mortem passes a sanity read.

## Deployment Implications
Not deploy-affecting.

## Completion Evidence Required
- Fixture directory exists with README documenting seeded conditions.
- Trace log captured under `skills/development-harness/scripts/tests/fixtures/self-test/` showing batch ≥2, the conflict, the scope violation.
- `POST-MORTEM.md` exists with the wall-clock data table.
- `references/parallel-execution.md` contains a link to the post-mortem.

## Rollback / Failure Considerations
If the self-test uncovers a blocker-level bug, halt the roadmap, file an issue via `/inject-harness-issues`, fix the bug, re-run the self-test. Do not mark this phase complete until the self-test is green end-to-end.

## Status
pending
