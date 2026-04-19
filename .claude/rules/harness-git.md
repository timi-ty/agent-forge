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
- Open a PR for every completed unit (small PRs)
- Merge strategy: squash merge
- Review policy: AI review via the installed `code-review` skill during phase completion (Step 9 of the invoke flow)
- Delegate commit/PR creation to the installed `commit-agent-changes` skill when available
- Never merge a PR without explicit user approval — surface the PR URL and wait

## Dogfood reminder
- Edits go to `skills/development-harness/**` (the canonical source), not `.harness/scripts/**` (the frozen runtime copy)
