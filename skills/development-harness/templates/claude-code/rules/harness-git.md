---
description: Git, PR, and merge policy for harness-managed work
paths:
  - "**/*"
---

# Git & PR Policy

## Branching
- Follow branch convention from .harness/config.json (default: feat/*, fix/*, chore/*)
- One branch per phase or logical unit group

## Commits
- Follow commit convention from config (default: conventional commits)
- Each completed unit or small group results in a commit
- Never reference AI/agent/Cursor/Claude Code in commit messages

## Pull Requests
- Open a PR when a phase or significant unit group completes.
- PR size follows the config preference (default: small).
- Run the internal review checklist before merging.
- If the `code-review` skill is installed, delegate review to it and fix any blocking findings before merge.
- If the `commit-agent-changes` skill is installed, use it for PR creation.
- **Autonomous merge:** once review passes, CI (if configured) is green, and — for deploy-affecting phases — the deployment truth gate has cleared, the harness proceeds with the squash merge and advances. Do not pause for per-PR confirmation. Still never force-push to the default branch, never bypass hooks, and never merge past a red reviewer or a failing gate.
