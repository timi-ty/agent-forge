---
description: Validation hierarchy and evidence requirements
paths:
  - "**/*"
---

# Validation Policy

## Hierarchy (lowest to highest confidence)
1. Static checks (linter, type checker)
2. Unit tests
3. Integration tests
4. E2E tests
5. CI checks
6. Deployed smoke checks
7. Deployed E2E

## Evidence Rules
- Every completed unit must have at least one validation evidence entry
- Evidence must be specific: "tests/auth.test.ts passes (12/12)" not "tests pass"
- Deploy-affecting phases require layers 5+ before completion
- If deployment verifier is not configured, deploy-affecting phases are blocked
