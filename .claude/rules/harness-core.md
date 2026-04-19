---
description: Core development harness operational rules
paths:
  - "**/*"
---

# Development Harness Core Rules

## Harness State
- Before modifying any harness file (.harness/*, PHASES/*), read .harness/ARCHITECTURE.md
- The authoritative source for "what to do next" is .harness/phase-graph.json via select_next_unit.py
- state.json is a runtime snapshot; phase-graph.json is canonical for phase/unit truth
- checkpoint.md is human-readable summary -- do not treat it as authoritative data

## Ownership
- Files with harness- prefix in .claude/rules/ are harness-owned
- Files in .harness/ and PHASES/ are harness-owned
- ROADMAP.md and all application source code are product-owned -- never modify without explicit user approval
- Check .harness/manifest.json before modifying any file to verify ownership

## Quality
- Run validation (linter, tests) after every code change
- Never mark a unit complete without validation evidence recorded in phase-graph.json
- Never mark a deploy-affecting phase complete without deployment verification
