# Harness Checkpoint

## Last Completed
{{LAST_COMPLETED_DESCRIPTION}}

## What Failed (if anything)
{{FAILURES_OR_NONE}}

## What Is Next
{{NEXT_UNIT_DESCRIPTION}}

## Blocked By
{{BLOCKERS_OR_NONE}}

## Evidence
{{EVIDENCE_SUMMARY}}

## Open Questions
{{QUESTIONS_OR_NONE}}

## Batch (current or last)

Reflects `state.execution.fleet`. When `mode == "idle"` and no batch has run yet, render `Batch ID: none`, `Mode: idle`, empty unit table, and "No conflicts." under Conflicts. Otherwise render the in-flight or most-recently-completed batch.

- **Batch ID:** {{BATCH_ID_OR_NONE}}
- **Mode:** {{FLEET_MODE}}

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|
{{BATCH_UNIT_ROWS_OR_NONE}}

### Conflicts
{{BATCH_CONFLICTS_OR_NONE}}

---
*Updated: {{TIMESTAMP}}*
