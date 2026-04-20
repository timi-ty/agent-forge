# Harness Checkpoint

## Last Completed
**unit_045 (PHASE_011):** [architecture.md](skills/development-harness/references/architecture.md) gained a new top-level "Parallel Execution Model" section.

### What landed
Nine sub-sections placed between "Batch Semantics" and "Git Integration":

1. **When to enable parallelism** — config knobs + 3-way unit-candidacy gate (`parallel_safe` + `depends_on` satisfied + non-empty `touches_paths` when `require_touches_paths`).
2. **Worktree-per-unit layout** — `.harness/worktrees/<batch_id>/<unit_id>/` + `harness/<batch_id>/<unit_id>` branches + `WORKTREE_UNIT.json` sentinel.
3. **Orchestrator / sub-agent boundary** — `Agent(subagent_type: "harness-unit")` + tight allowlist + "sub-agent's self-report never trusted for blast radius" invariant.
4. **Frontier + overlap check** — `select_next_unit.py --frontier` + `compute_parallel_batch.py` + 5 packing constraints (including overlap matrix via `fnmatch`).
5. **Dispatch → wait → merge lifecycle** — `idle` / `dispatched` / `merging` fleet.mode transitions + scope check BEFORE merge attempt + stop-hook-never-sees-partial-fleet invariant.
6. **Conflict strategies** — `abort_batch` (default) vs `serialize_conflicted` + cross-link to `phase-contract.md` scope-violation always-on rule.
7. **Merge serialization via `.harness/.lock`** — `O_EXCL` mutex + stale-lock takeover.
8. **Safety rails — session kill switch** — `safety_rails.py` + `.parallel-disabled` + 2-failure threshold + session-scoped clearing.
9. **Observability** — four `.harness/logs/<batch_id>/` artifacts (batch.json, `<unit_id>.md`, merge.log, validation.log) + best-effort semantics + `/harness-state` integration.

Concludes with forward link to `parallel-execution.md` (unit_047) for the full dispatch lifecycle + conflict-strategy catalogue.

### Grounding
Every claim in the new section is verified against a specific file in the repo — `dispatch_batch.py` (WORKTREE_UNIT.json seeding, atomic teardown), `merge_batch.py` (pre-merge scope check, lock acquisition), `compute_parallel_batch.py` (greedy pack + overlap matrix), `safety_rails.py` (kill-switch write), `_MergeLock` (stale-lock takeover). This is a true summary of what the code does, not aspirational documentation.

### New regression test
[test_architecture_parallel_section.py](skills/development-harness/scripts/tests/test_architecture_parallel_section.py) — 10 cases in `TestArchitectureParallelExecutionSection`:
1. Section heading present.
2. "When to enable" sub-heading + `config.execution_mode.parallelism` + `parallel_safe` + `depends_on` + `touches_paths` references.
3. "Worktree-per-unit layout" sub-heading + path/branch templates + `WORKTREE_UNIT.json`.
4. "Orchestrator / sub-agent boundary" sub-heading + `subagent_type: "harness-unit"` + allowlist callouts + "self-report never trusted" invariant.
5. "Frontier + overlap check" sub-heading + selector/compute script names + overlap matrix naming + `fnmatch`.
6. "Dispatch → wait → merge lifecycle" sub-heading + all three fleet.mode states (accepts `x`/"x" framing) + "BEFORE the merge attempt" timing.
7. "Conflict strategies" sub-heading + both strategy names + default marker + cross-link to `phase-contract.md`.
8. `.harness/.lock` + `O_EXCL` referenced.
9. `.parallel-disabled` + `safety_rails.py` + all four log artifacts referenced.
10. **Position-order assertion** — new section index falls between "Batch Semantics" and "Git Integration" (catches duplicates or misplacements).

Initial run caught an overly-strict `"dispatched"` assertion expecting double-quote framing; relaxed to accept either `` `x` `` or `"x"` for stylistic flexibility.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_046 (PHASE_011):** update [references/phase-contract.md](skills/development-harness/references/phase-contract.md) to document the required unit fields `depends_on`, `touches_paths` (when `parallel_safe: true`), and `parallel_safe`. Add a "Decomposing a phase for parallelism" subsection that walks through how to partition a phase into parallel-safe units.

The existing phase-contract.md already has the "Scope-Violation Enforcement Policy" section from unit_039 — unit_046 extends the Units of Work contract with the parallelism-specific fields and adds the decomposition guidance.

Validation: grep for new subsections + structural presence test similar to unit_045.

## Blocked By
None.

## Evidence
- [skills/development-harness/references/architecture.md](skills/development-harness/references/architecture.md): new "Parallel Execution Model" section (~120 new lines, 9 sub-sections).
- [skills/development-harness/scripts/tests/test_architecture_parallel_section.py](skills/development-harness/scripts/tests/test_architecture_parallel_section.py): new 160-line test module, 10 cases.
- `python -m py_compile` → 0 (~0.1s) on new test file.
- `python -m unittest skills.development-harness.scripts.tests.test_architecture_parallel_section -v` → **10/10** (0.003s).
- `python -m unittest discover skills/development-harness/scripts/tests` → **253/254** + 1 OS skip in 37.8s (up from 244).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, **resolved 2026-04-20**): Windows Python-detection. Fixed in unit_bugfix_001.
- **ISSUE_002** (high, **resolved 2026-04-20**): Claude Code Stop-hook one-shot continuation. Fixed in unit_bugfix_002.

All tracked issues resolved.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_011 PR opens after the last unit closes.
- **Branch:** `feat/phase-011-documentation`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 45 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_011 progress: **3/? units done** (bugfix_001 + bugfix_002 + 045). Remaining: 046 (phase-contract updates), 047 (new parallel-execution.md), 048 (unit_bugfix_001 reference — may already be done).
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → 206 → 210 → 215 → 222 → 223 → 228 → 244 → **254** across phases so far.

## Batch (current or last)

Reflects `state.execution.fleet`.

- **Batch ID:** none
- **Mode:** idle

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|

### Conflicts
No conflicts.

---
*Updated: 2026-04-20T10:40:00Z*
