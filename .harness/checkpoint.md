# Harness Checkpoint

## Last Completed
**unit_052 (PHASE_012):** [SKILL.md](skills/development-harness/SKILL.md) gained a new "Version upgrades" section placed between "Python Detection" and "Key Principle".

### Section content
Three numbered steps documenting the upgrade path:
1. **Re-run `/create-development-harness`** when `schema_version` bumps (v1 → v2, etc.) to regenerate `.harness/` artifacts at the new schema version.
2. **`ROADMAP.md` and `PHASES/*.md` are preserved** — the recreate flow reads them and rebuilds the harness around them. Real product/planning work is never regenerated from scratch (this is the claim that makes the upgrade path palatable).
3. Lists the regenerated harness-owned files explicitly (`state.json`, `phase-graph.json`, `checkpoint.md`, `manifest.json`, scripts, workspace commands, hook/rule files) so users with hand-edits know those edits will be lost.

Followed by the **load-bearing paragraph** (verbatim per acceptance criterion):
> **No migration script is provided by design.** The cost of a reliable general-purpose migration (covering every schema-version delta across every downstream file) exceeds the cost of regenerating with `ROADMAP.md` + `PHASES/*.md` as the preserved inputs.

Cross-links to `config.execution_mode.versioning.break_on_schema_bump` (the `break → true` default from unit_048) so users who prefer in-place migration attempts know which knob to flip (`break_on_schema_bump: false`) AND know upfront that the harness ships no migration tooling to back that choice up.

### New regression test
[test_skill_md_version_upgrades.py](skills/development-harness/scripts/tests/test_skill_md_version_upgrades.py) — 8 cases across 3 classes:

- **TestVersionUpgradesSectionPresent (2)** — heading present + position-order assertion (section must come BEFORE "Key Principle" so users hitting the schema-mismatch error see the upgrade path before the closing philosophical summary).
- **TestVersionUpgradesSubstantiveClaims (5)** — pins all 5 acceptance-criterion tokens: `/create-development-harness` + "Re-run" verb; `ROADMAP.md` + `PHASES/*.md` + "preserved" claim; verbatim "no migration script is provided by design" (lowercase match); cost argument presence; `break_on_schema_bump` config knob mention + `true` default.
- **TestVersionUpgradesListsRegeneratedFiles (1)** — pins that all 4 core regenerated files (`state.json`, `phase-graph.json`, `checkpoint.md`, `manifest.json`) are named so hand-edit users aren't surprised.

## What Failed (if anything)
None.

## What Is Next
**Complete unit_053 (PHASE_012):** update [commands/update.md](skills/development-harness/commands/update.md) and [templates/workspace-commands/update-development-harness.md](skills/development-harness/templates/workspace-commands/update-development-harness.md) to:

1. Detect `schema_version` mismatch between the installed `.harness/` and the installed skill.
2. Emit a pointer to `/create-development-harness` with a one-line explanation.
3. Do NOT attempt auto-migration.

Both docs must instruct the mismatch detection + pointer behavior; a v1 fixture test must assert the message is emitted. Validation: `python -m unittest skills.development-harness.scripts.tests.test_update_command` + grep.

This is the **LAST unit of PHASE_012**. After it lands → open the phase PR → run `code-review` → squash-merge per autonomous-merge authorization → cut PHASE_013.

## Blocked By
None.

## Evidence
- [skills/development-harness/SKILL.md](skills/development-harness/SKILL.md): new "Version upgrades" section.
- [skills/development-harness/scripts/tests/test_skill_md_version_upgrades.py](skills/development-harness/scripts/tests/test_skill_md_version_upgrades.py): new 150-line module, 8 cases.
- `python -m py_compile` → 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.test_skill_md_version_upgrades -v` → **8/8** (0.002s).
- `python -m unittest discover skills/development-harness/scripts/tests` → **311/312** + 1 OS skip in 38.2s (up from 304).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, **resolved 2026-04-20**): Windows Python-detection. Fixed in unit_bugfix_001.
- **ISSUE_002** (high, **resolved 2026-04-20**): Claude Code Stop-hook one-shot continuation. Fixed in unit_bugfix_002.

All tracked issues resolved.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_012 PR opens after unit_053 (last unit).
- **Branch:** `feat/phase-012-release-readiness`.
- **Merge:** squash; autonomous per [harness-git.md](.claude/rules/harness-git.md).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 50 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_012 progress: **2/3 units done** (051 readiness checklist, 052 SKILL.md version-upgrades note). Remaining: 053 update-command schema-mismatch handling.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → 206 → 210 → 215 → 222 → 223 → 228 → 244 → 254 → 265 → 275 → 286 → 291 → 304 → **312** across phases so far.

## Batch (current or last)

Reflects `state.execution.fleet`.

- **Batch ID:** none
- **Mode:** idle

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|

### Conflicts
No conflicts.

---
*Updated: 2026-04-20T12:50:00Z*
