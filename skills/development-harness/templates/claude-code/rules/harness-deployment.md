---
description: Deployment verification policy
paths:
  - "**/*"
---

# Deployment Policy

## Truth Hierarchy
- Local test success = confidence
- CI passing = stronger confidence
- Deployed verification = truth

## Rules
- Check .harness/config.json for deployment target and verification method
- No deploy-affecting phase may be marked complete without deployed verification
- If no deployment verifier is configured, flag it as a blocker
- Record deployment evidence in phase-graph.json unit validation_evidence
- Smoke test URL, health endpoint, or deployed E2E are acceptable verifiers
