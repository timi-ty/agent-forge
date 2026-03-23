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
- Open PR when a phase or significant unit group completes
- PR size follows config preference (default: small)
- Run internal review checklist before merging
- If code-review skill is installed, delegate review to it
- If commit-agent-changes skill is installed, use it for PR creation
