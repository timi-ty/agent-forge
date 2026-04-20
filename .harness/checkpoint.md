# Harness Checkpoint

## Last Completed
**unit_053 (PHASE_012) — PHASE_012 CLOSED.** `/update-development-harness` now refuses schema mismatches and redirects to `/create-development-harness`.

### What landed
[commands/update.md](skills/development-harness/commands/update.md) gained a **Step 0: Schema Version Precheck** at the top of the steps list that runs `validate_harness.py` first and branches on output:

- **Exit 0** → proceed to normal update flow.
- **Exit 1 with `/create-development-harness` in errors** → surface the verbatim advisory: "The harness on disk is on an older schema than the installed skill. Re-run `/create-development-harness`. `ROADMAP.md` and `PHASES/*.md` are preserved. See `SKILL.md` § 'Version upgrades' — **no migration script is provided by design**." Explicit "Do NOT attempt in-place migration. Do NOT enter Plan Mode." forbidding.
- **Exit 1 without pointer** → different structural problem, report and stop.

Cleanup of contradictory content:
- Pre-existing "Schema migration" row in the Categorize-the-Change table → **removed**, replaced with a blockquote noting schema_version bumps are NOT a category.
- Pre-existing Step 10 "Schema Migration" → rewritten to **"Schema Migration (not supported)"** with the refusal + redirect to `/create-development-harness`.

[templates/workspace-commands/update-development-harness.md](skills/development-harness/templates/workspace-commands/update-development-harness.md) mirrors the edits. The workspace variant already carried a "Step 0: Resolve tool paths", so the precheck is numbered **Step 0.5** (sits between tool-path resolution and the main procedure).

### PHASE_012 at a glance
| Unit | Done | Evidence |
|------|------|----------|
| unit_051 | Parallelism readiness checklist extended with 3 new bullets + 2 sub-headings | 13 tests pin structure + regression guard |
| unit_052 | SKILL.md "Version upgrades" section | 8 tests pin position + 5 acceptance tokens + regenerated-files listing |
| unit_053 | update-command schema-mismatch precheck + refusal + v1 fixture test | 9 tests (2 v1-fixture user-flow + 7 doc-shape contract) |

Suite: 291 → 321 across the phase (1 Windows skip).

### PR review checklist (pr-review-checklist.md)
- [x] All 3 units have `validation_evidence` in phase-graph.json
- [x] No linter/type errors (stdlib-only Python)
- [x] Codebase patterns matched
- [x] Unit tests pass 320/321 + 1 OS skip
- [x] Not deploy-affecting (skill distribution repo)
- [x] Phase doc + checkpoint + state current

### New regression test
[test_update_command.py](skills/development-harness/scripts/tests/test_update_command.py) — 9 cases across 2 classes:

- **TestV1FixtureTripsSchemaMismatch (2)** — seeds a v1-shaped harness workspace (all 4 JSON files at `schema_version: "1.0"`) and invokes `validate_harness.py` via subprocess exactly as Step 0/0.5 instructs. Asserts returncode 1 + `valid: false` + `/create-development-harness` in joined errors + all 4 filenames (`config.json`, `state.json`, `manifest.json`, `phase-graph.json`) appear in errors.
- **TestUpdateDocsCarryPrecheckContract (7)** — pins the doc-shape contract across BOTH docs: Schema Version Precheck section exists, `validate_harness.py` named as the precheck tool, `/create-development-harness` + "older schema" pointer language, verbatim "no migration script is provided by design" (lowercase match), `SKILL.md` § Version upgrades cross-link, "Do NOT attempt" forbidding, and a long-doc-specific assertion that the pre-unit_053 "Schema migration" table row is gone.

## What Failed (if anything)
None.

## What Is Next
**Open PHASE_012 PR** (`feat/phase-012-release-readiness` → `main`), run the `code-review` skill, squash-merge per [harness-git.md](.claude/rules/harness-git.md) autonomous-merge authorization.

**Then PHASE_013 `unit_054`:** create [skills/development-harness/scripts/tests/fixtures/self-test/](skills/development-harness/scripts/tests/fixtures/) — throwaway workspace with a 2-phase / 6-unit mini-CRUD roadmap designed to exercise a batch ≥ 2 plus one merge conflict and one scope violation. This starts the harness-self-test phase — the harness uses its own parallel machinery against a throwaway project to verify end-to-end correctness.

## Blocked By
None.

## Evidence
- [skills/development-harness/commands/update.md](skills/development-harness/commands/update.md): Step 0 Schema Version Precheck + cleanup of contradictory content.
- [skills/development-harness/templates/workspace-commands/update-development-harness.md](skills/development-harness/templates/workspace-commands/update-development-harness.md): mirrored edits.
- [skills/development-harness/scripts/tests/test_update_command.py](skills/development-harness/scripts/tests/test_update_command.py): new 230-line module, 9 cases.
- `python -m py_compile` → 0 (~0.1s).
- `python -m unittest skills.development-harness.scripts.tests.test_update_command -v` → **9/9** (0.2s).
- `python -m unittest discover skills/development-harness/scripts/tests` → **320/321** + 1 OS skip in 38.3s (up from 312).

## Open Questions
None.

## Tracked Issues
- **ISSUE_001** (high, **resolved 2026-04-20**): Windows Python-detection. Fixed in unit_bugfix_001.
- **ISSUE_002** (high, **resolved 2026-04-20**): Claude Code Stop-hook one-shot continuation. Fixed in unit_bugfix_002.

All tracked issues resolved.

## Commit Policy (recorded)
- **PR cadence:** one PR per phase. PHASE_012 PR opens now (phase closed).
- **Branch:** `feat/phase-012-release-readiness` → squash-merge to `main`.
- **Next branch:** `feat/phase-013-harness-self-test` (after PHASE_012 squashes in).

## Reminders
- Skill edits only in `skills/development-harness/**`. `.harness/scripts/` stays frozen.
- `session_count` is 51 / `loop_budget` 12 — `/loop` remains the driver.
- PHASE_012 progress: **3/3 units done** — phase CLOSED.
- Test-suite count: 65 → 83 → 106 → 109 → 118 → 134 → 144 → 160 → 164 → 169 → 171 → 173 → 178 → 183 → 198 → 201 → 204 → 206 → 210 → 215 → 222 → 223 → 228 → 244 → 254 → 265 → 275 → 286 → 291 → 304 → 312 → **321** across phases so far.

## Batch (current or last)

Reflects `state.execution.fleet`.

- **Batch ID:** none
- **Mode:** idle

| Unit | Phase | Status | Branch | Started | Ended |
|------|-------|--------|--------|---------|-------|

### Conflicts
No conflicts.

---
*Updated: 2026-04-20T13:20:00Z*
