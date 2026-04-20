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

| Field | Description | Required |
|-------|-------------|----------|
| **id** | Unique identifier (e.g., `unit_001`) | always |
| **description** | What the unit accomplishes | always |
| **acceptance criteria** | Concrete conditions for completion | always |
| **validation method** | How the validator proves completion (e.g., "pytest tests/unit/test_foo.py" or "npm run lint") | always |
| **depends_on** | List of unit ids that must be `completed` before this unit is eligible. Empty list means "only phase-level dependencies gate this unit". Enforced by `compute_frontier` in [scripts/select_next_unit.py](../scripts/select_next_unit.py). | always (empty list allowed) |
| **parallel_safe** | `true` iff the unit can run concurrently with other parallel-safe units in the same batch. Requires the unit be self-contained (no shared files with siblings, no cross-unit git state mutation beyond its own commits). Units with `parallel_safe: false` are excluded from parallel batches by [scripts/compute_parallel_batch.py](../scripts/compute_parallel_batch.py) and always execute in the in-tree fast path. | always (default `false`) |
| **touches_paths** | List of glob patterns declaring every file the unit may create or modify. Non-empty required when `parallel_safe: true` AND `config.execution_mode.parallelism.require_touches_paths: true` (the default). The orchestrator merge-time scope check rejects any changed file that matches none of these globs — see "Scope-Violation Enforcement Policy" below. | required when `parallel_safe: true` (under default config) |

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

---

## Decomposing a phase for parallelism

A phase is a candidate for parallel execution when it can be split into **independent, disjoint-file** units. This section is the checklist a phase author walks through before declaring units `parallel_safe: true`. See [references/architecture.md](./architecture.md) "Parallel Execution Model" for the runtime view of how a parallel batch actually executes.

### Step 1: Draw the dependency graph

Write out the unit ids and the strict `depends_on` relationships between them. A unit depends on another only if it **must** run after — not "feels like it should". Over-declaring dependencies collapses parallelism back to sequential; under-declaring them produces merge conflicts or broken state.

- **Depends_on types that are real:** unit B reads a file unit A creates; unit B references a symbol defined by unit A; unit B's tests import unit A's module.
- **Depends_on types that are NOT real:** "B feels like it should come after A logically." If B never reads A's output and never shares files with A, declare them independent.

### Step 2: Identify each unit's blast radius

For each unit, list every file it will create or modify. This is the `touches_paths` value. Use globs liberally — `src/auth/**` is fine — but declare the actual scope, not an aspirational one. The scope check runs on the real diff, so over-declaring globs is safe (tolerates what the unit doesn't touch) but under-declaring them fails the merge (rejects work the unit genuinely did).

Two heuristics:

1. **One directory per unit** is the cleanest shape. A unit that owns `src/auth/**` and another that owns `src/billing/**` are trivially parallel-safe.
2. **Shared test utilities and shared types files are the usual hazard.** When two units both want to extend `src/types.ts` or `tests/fixtures.ts`, they are not parallel-safe — put them in sequential order via `depends_on` or merge the units.

### Step 3: Check for overlap

With `touches_paths` declared on every candidate, verify no two units in the same frontier share a declared path. [scripts/compute_parallel_batch.py](../scripts/compute_parallel_batch.py) runs an `fnmatch`-based overlap matrix and will reject overlapping pairs with `reason: "touches_overlap: <other_unit_id>"`. The overlap matrix is conservative — if `src/auth/**` and `src/auth/helpers/*.ts` both appear on sibling units, they overlap even if the actual files are disjoint.

If you see overlap reports in `batch.excluded` that feel wrong, the fix is always to narrow the globs, not to disable the check.

### Step 4: Set `parallel_safe` deliberately

`parallel_safe: true` is a **declaration of independence**, not a performance hint. Set it only when:

- `touches_paths` is accurate and disjoint from every other parallel-safe unit in the phase.
- The unit writes no files outside its worktree (enforced by the sub-agent's tool allowlist, but worth double-checking the description).
- The unit runs no orchestrator-level side effects (no git push, no external API calls that other units depend on).
- The unit's validation passes against a fresh worktree created off `HEAD`.

When in doubt, leave `parallel_safe: false`. A phase with 6 sequential units that validates correctly is better than 6 parallel units that collide on merge.

### Step 5: Dry-run the batch

Before running the phase, run:

```
$PY .harness/scripts/select_next_unit.py --frontier | $PY .harness/scripts/compute_parallel_batch.py --input - --config .harness/config.json
```

Inspect the resulting `batch` and `excluded` lists. Every candidate should either land in `batch` or appear in `excluded` with a reason that matches your intent (`not_parallel_safe`, `capacity_cap`, `touches_overlap`, `cross_phase`). Surprises here are cheaper to fix than surprises at merge time.

### Anti-patterns

- **A phase with a single "set up everything" unit followed by N parallel units** — the setup unit is usually a sign that the parallel units aren't actually independent. Either they share the setup output (so make them depend on it), or the setup belongs in an earlier phase.
- **Declaring `parallel_safe: true` to signal "this is fast" rather than "this is independent"** — the harness packs batches greedily, so a fast-but-dependent unit just delays the whole batch's merge. Use `depends_on` to express ordering.
- **Globs that cover shared files** — e.g., two units both declaring `touches_paths: ["**/*.md"]`. The overlap matrix catches this, but it is easier to catch at design time.
