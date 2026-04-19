# PHASE_009: Safety Rails and Automatic Fallback

## Objective
Add the degradation paths that make parallel execution safe to enable on real projects: a session kill switch, guaranteed scope-violation enforcement, and lock-based merge serialization.

## Why This Phase Exists
Parallelism can fail in ways sequential execution cannot: bad touches_paths declarations, ambiguous sub-agent reports, concurrent merge collisions. Without automatic degradation and explicit policy, a single bad batch can cascade into repeated failures. These rails catch problems early and fall back gracefully.

## Scope
- Session-scoped kill switch: if a batch fails with `category: "scope_violation"` or `"ambiguity"` more than once in the same invoke session, write `.harness/.parallel-disabled` and run the rest of the session as batch-of-1 (in-tree). The flag is cleared when `.invoke-active` is cleared.
- Verify batch-of-1 uses the same in-tree path as `parallelism == false` (no special-case branch in the invoke doc). Assertion test.
- Scope-violation enforcement is always on, regardless of `require_touches_paths`. Document this policy in `skills/development-harness/references/phase-contract.md`.
- Concurrent merge serialization via `.harness/.lock` (introduced in PHASE_005); verify by contention test.
- Default `conflict_strategy: "abort_batch"`. `serialize_conflicted` is documented but not default.

> ⚠️ **Edit target:** `skills/development-harness/**` only.

## Non-goals
- Policy changes to the sub-agent tool allowlist — PHASE_006 owns that.
- Cross-session kill switches — session-scoped only.

## Dependencies
- PHASE_007 (the invoke flow where kill switch is read/written).

## User-visible Outcomes
- Two bad batches in a session → remaining work auto-downgrades to in-tree; user sees a clear blocker in the checkpoint.
- Scope violations are rejected every time, even if `require_touches_paths: false`.
- Concurrent merge attempts serialize cleanly.

## Units of Work

| ID | Description | Acceptance Criteria | Validation Method | Status |
|----|-------------|--------------------|--------------------|--------|
| unit_037 | Session kill switch `.harness/.parallel-disabled` | Written after 2 scope_violation/ambiguity failures in one session; read by invoke flow; cleared when `.invoke-active` is cleared | `python -m unittest skills.development-harness.scripts.tests.test_safety_rails` | pending |
| unit_038 | Verify batch-of-1 uses in-tree path (no special case) | Grep of invoke doc finds no "if batch_size == 1 then sequential path" branch; integration test asserts final state equivalence | grep + `test_safety_rails` | pending |
| unit_039 | Document scope-violation always-on policy in `references/phase-contract.md` | Policy statement added with rationale (trust boundary) | grep | pending |
| unit_040 | Concurrent merge serialization test | Two `merge_batch.py` invocations contend on `.harness/.lock`; second blocks until first completes; test exits 0 | `test_merge_batch` contention case (added in PHASE_005; verified here) | pending |

## Validation Gates
- **Layer 1:** Python syntax valid.
- **Layer 2:** Unit tests pass.

## Deployment Implications
Not deploy-affecting.

## Completion Evidence Required
- `test_safety_rails` exits 0.
- Grep confirms no residual batch-of-1-special-case language in the invoke doc.
- `references/phase-contract.md` contains the scope-violation always-on policy statement.

## Rollback / Failure Considerations
If the kill switch writes too eagerly, the user can `rm .harness/.parallel-disabled` to re-enable. If the lock causes deadlocks, detection requires stale-lock timeout logic (out of scope here; add an issue for follow-up).

## Status
pending
