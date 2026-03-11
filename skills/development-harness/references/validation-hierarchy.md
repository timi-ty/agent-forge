# Validation Hierarchy

Seven layers of validation apply before phases are marked complete. Each layer proves a different aspect of correctness. Lower layers are typically faster; higher layers are more comprehensive.

## Layer 1: Static Checks

| What it proves | Code passes linter, type checker, formatter |
| When it applies | Every phase that touches code |
| Evidence | Exit code 0 from linter/typechecker/formatter |
| Blocking | Yes |

## Layer 2: Unit Tests

| What it proves | Individual units/functions behave correctly in isolation |
| When it applies | When unit-testable code exists |
| Evidence | All unit tests pass (e.g., pytest, jest) |
| Blocking | Yes |

## Layer 3: Integration Tests

| What it proves | Components work together correctly |
| When it applies | When integration points exist |
| Evidence | Integration test suite passes |
| Blocking | Yes |

## Layer 4: E2E / Browser / Workflow Tests

| What it proves | End-to-end user flows work in test environment |
| When it applies | When user-facing flows exist |
| Evidence | E2E test suite passes (e.g., Playwright, Cypress) |
| Blocking | Yes |

## Layer 5: CI Checks

| What it proves | Code passes in CI pipeline (e.g., GitHub Actions) |
| When it applies | Every phase that touches code |
| Evidence | CI run successful; artifacts or logs available |
| Blocking | Yes |

## Layer 6: Deployed Smoke Checks

| What it proves | Deployed environment is reachable and basic health checks pass |
| When it applies | Deploy-affecting phases only |
| Evidence | Health endpoint returns OK; smoke test URL responds |
| Blocking | Yes for deploy-affecting phases |

## Layer 7: Deployed E2E

| What it proves | Full E2E against deployed environment succeeds |
| When it applies | Deploy-affecting phases only |
| Evidence | E2E suite passes against deployed URL |
| Blocking | Yes for deploy-affecting phases |

---

## Deployment Truth Policy

| Rule | Description |
|------|-------------|
| **No deploy without verifier** | No deploy-affecting phase may be marked complete without a configured deployment verifier. |
| **Layers 5+ required** | Deploy-affecting phases require evidence from layers 5, 6, and 7 when applicable. |
| **Local ≠ truth** | Local success is confidence; deployed verification is truth. |
| **Blocked if unconfigured** | If deployment verifier is not configured, deploy-affecting phases are blocked. |
