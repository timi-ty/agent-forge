---
description: Git, PR, and merge policy for harness-managed work
paths:
  - "**/*"
---

# Git & PR Policy (agent-forge bootstrap)

## Branching
- Convention: `<type>/<short-description>` (e.g., `feat/phase-001-schema-extend`, `fix/frontier-edge-case`)
- One branch per phase or per small group of tightly-coupled units within a phase
- Never push directly to main; always use a PR

## Commits
- Convention: conventional-commits (e.g., `feat(harness): extend phase-graph schema with depends_on`)
- Each completed unit results in a commit (PR size: small)
- Never reference AI / agent / Cursor / Claude Code in commit messages

## Pull Requests
- Open a PR when a phase (or tightly-coupled small group of units) completes (current cadence: one PR per phase — see `state.policy.pr_cadence`).
- Merge strategy: squash merge.
- Review policy: AI review via the installed `code-review` skill during phase completion (Step 9 of the invoke flow). Fix any blocking findings before merging.
- Delegate commit/PR creation to the installed `commit-agent-changes` skill when available.
- **Autonomous merge authorized.** Once the PR is opened, the code-review skill has passed, CI (if configured) is green, and — for deploy-affecting phases — the deployment truth gate has cleared, the harness squash-merges the PR and advances. Do not pause for per-PR confirmation; the user granted the harness blanket authorization to run push → review → merge until the roadmap goal is achieved. Still never `--force`-push to `main`, never `--no-verify`, never merge past a red reviewer or a failing gate.

## Dogfood reminder
- Edits go to `skills/development-harness/**` (the canonical source), not `.harness/scripts/**` (the frozen runtime copy)
