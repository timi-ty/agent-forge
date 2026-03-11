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
