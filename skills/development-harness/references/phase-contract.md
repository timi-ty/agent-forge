# Phase Document Contract

Every `PHASE_XXX_slug.md` file must conform to this contract. Phases are executable contracts, not planning notes. Each unit must have a validator.

## Required Sections

### Title and Objective

- Clear phase identifier.
- Single-sentence objective stating what the phase achieves.

### Why This Phase Exists

- Rationale for treating this as a distinct unit.
- Why it is not merged with adjacent phases.

### Scope

- Explicit list of included work.
- No ambiguity about what is in scope.

### Non-Goals

- Explicitly excluded work.
- Items deferred to other phases.

### Dependencies

- Which phases must complete first.
- Phase IDs or slugs for ordering.

### User-Visible Outcomes

- What users will see or experience when this phase completes.
- Measurable outcomes where possible.

### Units of Work

Ordered list of bounded, validator-backed tasks. Each unit must include:

| Field | Description |
|-------|-------------|
| **id** | Unique identifier (e.g., `unit_001`) |
| **description** | What the unit accomplishes |
| **acceptance criteria** | Concrete conditions for completion |
| **validation method** | How the validator proves completion (e.g., "pytest tests/unit/test_foo.py" or "npm run lint") |

### Validation Gates

- Which layers of the validation hierarchy apply to this phase.
- Reference to `validation-hierarchy.md` layers (1–7).

### Deployment Implications

- Whether this phase affects deployment.
- If yes, which deployment verifier applies.
- Deployment truth policy applies: no deploy-affecting phase completes without layers 5+ evidence.

### Completion Evidence Required

- What artifacts or evidence must exist before marking complete.
- Links to CI runs, logs, or deployed endpoints.

### Rollback or Failure Considerations

- What happens if validation fails.
- How to roll back or recover.
- Failure handling steps.

### Status

One of: `pending` | `in_progress` | `completed` | `blocked` | `failed`

---

## Contract Enforcement

- Phases must be executable: an agent can run units in order and validate each.
- Each unit must have a validator; no unit without a validation method is valid.
- Non-goals and scope must be explicit to avoid scope creep.

---

## Scope-Violation Enforcement Policy

**Scope-violation detection is always on, regardless of configuration.**

When a unit declares `touches_paths`, the orchestrator runs `git diff --name-only <merge-base>..<branch>` at merge time and rejects any changed file that matches none of the declared globs (via `fnmatch`). This check is implemented in [scripts/merge_batch.py](../scripts/merge_batch.py) `_scope_violations` and is invoked unconditionally from the merge loop whenever `WORKTREE_UNIT.json` carries a non-null `touches_paths` list. The sub-agent's self-report is never trusted for blast radius; the git diff is the source of truth.

### What `config.execution_mode.parallelism.require_touches_paths` does NOT do

`require_touches_paths` is an **admission-control** knob on [scripts/compute_parallel_batch.py](../scripts/compute_parallel_batch.py), not a merge-time enforcement toggle:

- `require_touches_paths: true` (default) — units without a `touches_paths` declaration are **excluded from the batch** (reason: `not_parallel_safe`). They stay eligible for sequential (batch-of-1, in-tree) execution.
- `require_touches_paths: false` — units without a `touches_paths` declaration **may enter a parallel batch**. For these units, the merge-time scope check is skipped (there is nothing to check against), but they otherwise follow the same worktree-dispatch-and-merge path.

Crucially, **`require_touches_paths: false` does not relax merge-time enforcement for units that DO declare `touches_paths`.** Once a declaration is present on a unit, the orchestrator enforces it at merge time — every time. There is no configuration that turns that check off.

### Rationale: trust boundary, not feature toggle

`touches_paths` is a **trust-boundary declaration**. The sub-agent that produces the unit's commits is untrusted (worktree-confined tool allowlist, no write access to `.harness/`, no git push/merge/rebase — see [templates/claude-code/agents/harness-unit.md](../templates/claude-code/agents/harness-unit.md)). The orchestrator's only guarantee that a sub-agent didn't step outside its lane is the diff against its declared globs.

If an adversarial or misbehaving sub-agent could disable the diff check by setting `require_touches_paths: false`, the declaration would mean nothing. So the policy is: `require_touches_paths` decides **whether a missing declaration is fatal at batch-compute time**; it does not decide **whether a present declaration is enforced at merge time**. The merge-time check reads only the worktree-sentinel's `touches_paths` list; it does not read `require_touches_paths`.

### Downstream consequences

- A scope violation is always a hard reject: `conflict.category: "scope_violation"`, `conflict_strategy` has no effect. See [scripts/merge_batch.py](../scripts/merge_batch.py) and the PHASE_005 unit_022 evidence in [phase-graph.json](../../../.harness/phase-graph.json).
- Scope violations count toward the session-scoped kill switch in [scripts/safety_rails.py](../scripts/safety_rails.py) (`COUNTED_CATEGORIES = ("scope_violation", "ambiguity")`). Two in one session → `.harness/.parallel-disabled` → remaining work auto-downgrades to the in-tree fast path, where the scope check runs against `git diff --name-only HEAD` inside the orchestrator turn itself.
- This policy is a **per-phase contract invariant**, not a per-phase decision. No phase doc may opt out of scope-violation enforcement.
