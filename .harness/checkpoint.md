# Harness Checkpoint

## Last Completed
**unit_057 (PHASE_013):** Wall-clock comparison run + 2 runtime bugs caught during implementation.

### What landed

**[TestWallClockParallelVsSequential](skills/development-harness/scripts/tests/integration/test_self_test_run.py)** — runs the Tasklet fixture driver twice in fresh temp repos:

- **Parallel:** `max_concurrent_units=3` (fixture default).
- **Sequential baseline:** `max_concurrent_units=1` — forces batch-of-1 throughout.

Both runs use worktree fan-out (dispatch + merge) so the only independent variable is batch size. Times each via `time.monotonic()` and writes a comparison markdown to [fixtures/self-test/wall-clock.md](skills/development-harness/scripts/tests/fixtures/self-test/wall-clock.md).

### Driver refactor
The 126-line in-class `_run_one_turn` method was refactored into a standalone `_drive_fixture` free function shared by both tests (unit_056's `TestSelfTestEndToEnd` and unit_057's `TestWallClockParallelVsSequential`).

### Two runtime bugs caught during implementation
**Bug 1 — `compute_frontier` missing-filter for `failed` status.** [select_next_unit.py:123](skills/development-harness/scripts/select_next_unit.py#L123) filters out `status == "completed"` but NOT `failed`. So after a scope-violation flips a unit to `failed`, `compute_frontier` keeps surfacing it on subsequent turns. Worked around at driver level (filter `failed` from the frontier before passing to `compute_batch`); the runtime fix is a separate follow-up.

**Bug 2 — Same-second turns share batch_id.** [compute_parallel_batch.py:112](skills/development-harness/scripts/compute_parallel_batch.py#L112) uses 1-second granularity for `_make_batch_id`. Multiple turns in the same second share a batch_id. Combined with Bug 1, this caused `git worktree add` to fail with exit 255 on re-dispatch of scope-violated units — the branch name `harness/<same-second-batch>/unit_b2` already existed from the preserved worktree. The Bug 1 workaround (filter `failed` from frontier) resolves the symptom.

### Scope-violation phase-graph flip
Both drivers (`_run_one_turn` and `_drive_fixture`) now flip scope-violation units to `status: "failed"` in the phase-graph — more correct terminal state than leaving them `pending` (where they'd be mistaken for work-in-progress). Updated unit_056's end-state assertion accordingly.

### Results
```
| Run        | max_concurrent_units | Turns | Batch sizes         | Wall-clock (s) |
|------------|----------------------|-------|---------------------|----------------|
| Parallel   | 3                    | 3     | [2, 1, 3]           | 1.97           |
| Sequential | 1                    | 6     | [1, 1, 1, 1, 1, 1]  | 2.00           |
```

Ratio **1.02x** — small because fake-commits are instantaneous. Turn count (3 vs 6) is the meaningful signal for this fixture. A real project with slow per-unit work will see a larger ratio since fixed overhead stays constant while expensive per-unit work overlaps.

### Shape assertions
Beyond wall-clock timings:
- Parallel run must have max batch ≥ 2.
- Sequential run must have all batches of size 1.
- **Both** runs record exactly one `unit_b2` scope violation (fixture property, not parallelism-config property).
- Sequential turns > parallel turns.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_058 (PHASE_013) — LAST UNIT OF THE ROADMAP:** write [POST-MORTEM.md](skills/development-harness/scripts/tests/fixtures/self-test/POST-MORTEM.md) with sections:

- **Setup** — fixture design, operator recipe.
- **Results** — embed the wall-clock.md table + trace.log highlights.
- **Papercuts** — the 2 runtime bugs caught in unit_057 (compute_frontier missing `failed` filter, 1-second batch_id granularity) with prescriptions.
- **Follow-ups** — file issues via `/inject-harness-issues` for the two bugs (or note they're scope for a future phase).

Add a link from [references/parallel-execution.md](skills/development-harness/references/parallel-execution.md) to the new post-mortem.

After unit_058 lands → open the PHASE_013 PR → run `code-review` → squash-merge. **PHASE_013 is the final phase of the roadmap; once it closes, the development-harness skill upgrade is complete.**

## Blocked By
None.

## Evidence
- [skills/development-harness/scripts/tests/integration/test_self_test_run.py](skills/development-harness/scripts/tests/integration/test_self_test_run.py): extended with TestWallClockParallelVsSequential + `_drive_fixture` free-function refactor.
- [skills/development-harness/scripts/tests/fixtures/self-test/wall-clock.md](skills/development-harness/scripts/tests/fixtures/self-test/wall-clock.md): new comparison table.
- `python -m py_compile` → 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.integration.test_self_test_run -v` → **2/2** in 6.4s.
- `python -m unittest discover skills/development-harness/scripts/tests` → **346/347** + 1 OS skip in 45.2s (up from 346).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, **resolved 2026-04-20**): Windows Python-detection. Fixed in unit_bugfix_001.
- **ISSUE_002** (high, **resolved 2026-04-20**): Claude Code Stop-hook one-shot continuation. Fixed in unit_bugfix_002.

All tracked issues resolved. Two **new** runtime bugs surfaced by unit_057 (compute_frontier missing-filter + batch_id 1-sec granularity) will be filed in unit_058's post-mortem as follow-ups.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_013 PR opens after unit_058.
- **Branch:** `feat/phase-013-harness-self-test`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 55 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_013 progress: **4/5 units done** (054 fixture, 055 artifacts, 056 self-test, 057 timings). Remaining: 058 POST-MORTEM.md + parallel-execution.md link.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → 206 → 210 → 215 → 222 → 223 → 228 → 244 → 254 → 265 → 275 → 286 → 291 → 304 → 312 → 321 → 332 → 345 → 346 → **347** across phases so far.

## Batch (current or last)

Reflects `state.execution.fleet`.

- **Batch ID:** none
- **Mode:** idle

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|

### Conflicts
No conflicts.

---
*Updated: 2026-04-20T15:05:00Z*
