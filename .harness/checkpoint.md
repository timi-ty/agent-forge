# Harness Checkpoint

## Last Completed
**unit_039 (PHASE_009):** Scope-violation always-on policy documented in [references/phase-contract.md](skills/development-harness/references/phase-contract.md) with trust-boundary rationale.

- **Policy statement:** scope-violation detection (`git diff --name-only` vs merge-base + `fnmatch` against declared `touches_paths`) runs **unconditionally**, regardless of any configuration knob. Implemented in [merge_batch.py](skills/development-harness/scripts/merge_batch.py) `_scope_violations` (lines 233–252) and invoked from the merge loop (lines 400–411) whenever `WORKTREE_UNIT.json` carries a non-null `touches_paths` list. The sub-agent's self-report is never trusted for blast radius.
- **What `require_touches_paths` does NOT do:** it is an admission-control knob on [compute_parallel_batch.py:148](skills/development-harness/scripts/compute_parallel_batch.py#L148) that decides whether a unit *lacking* a `touches_paths` declaration gets excluded from a parallel batch. It does **not** toggle merge-time enforcement — once a declaration is present, the orchestrator enforces it every time.
- **Trust-boundary rationale:** `touches_paths` is a trust-boundary declaration, not a feature toggle. The sub-agent is untrusted (worktree-confined tool allowlist, no push/merge/rebase — see [harness-unit.md](skills/development-harness/templates/claude-code/agents/harness-unit.md)), and the git diff against declared globs is the orchestrator's only guarantee that the sub-agent didn't step outside its lane.
- **Downstream consequences documented:** scope violation is a hard reject regardless of `conflict_strategy`; counts toward `COUNTED_CATEGORIES` in [safety_rails.py](skills/development-harness/scripts/safety_rails.py) (two in one session → `.parallel-disabled` kill switch); is a per-phase contract invariant that no phase doc may opt out of.
- **New regression test:** `TestScopeViolationAlwaysOnPolicy` class in [test_safety_rails.py](skills/development-harness/scripts/tests/test_safety_rails.py) (3 cases). Pins (a) the policy section + "always on, regardless of configuration" phrasing, (b) admission-control classification + `compute_parallel_batch` mention + admission-vs-merge-time contrast, and (c) the trust-boundary rationale with "sub-agent" and "diff" keywords.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_040 (PHASE_009):** concurrent merge serialization test — two `merge_batch.py` invocations contend on `.harness/.lock`; the second blocks until the first completes. Acceptance is largely pre-satisfied by PHASE_005 unit_023's `TestLockContention.test_second_acquirer_blocks_until_first_releases` in [test_merge_batch.py](skills/development-harness/scripts/tests/test_merge_batch.py) (spawns a subprocess that acquires the lock, verifies the main process blocks on `acquire` until the subprocess releases). unit_040's job is to grep-verify that test is still present + covers the full contention contract, and add any missing assertions (e.g., lock file location pinned, timeout behavior tested, second acquirer observes post-first-merge state).

## Blocked By
None.

## Evidence
- [skills/development-harness/references/phase-contract.md](skills/development-harness/references/phase-contract.md): new "Scope-Violation Enforcement Policy" section appended after "Contract Enforcement".
- [skills/development-harness/scripts/tests/test_safety_rails.py](skills/development-harness/scripts/tests/test_safety_rails.py): 3 new cases in `TestScopeViolationAlwaysOnPolicy`.
- `python -m py_compile` on changed test file exits 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.test_safety_rails.TestScopeViolationAlwaysOnPolicy -v` → **3/3** in 0.001s.
- `python -m unittest discover skills/development-harness/scripts/tests` → **204/204** (up from 201) in 41.0s.

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, open): Windows Python-detection in create.md Phase 5. Skill-source fix scheduled as `unit_bugfix_001` at the head of PHASE_011.
- **ISSUE_002** (high, open): Claude Code Stop-hook continuation is one-shot. Skill-source fix scheduled as `unit_bugfix_002` at the head of PHASE_011.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_009 PR opens after unit_040 (closes the phase).
- **Branch:** `feat/phase-009-safety-rails`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 37 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_009 progress: **3/4 units done** (037 kill switch, 038 batch-of-1 equivalence, 039 scope-violation always-on policy). Remaining: 040 concurrent merge serialization test.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → **204** across phases so far.

---
*Updated: 2026-04-20T07:00:00Z*
