# Command: Create Development Harness

**Mode:** Switch to Plan Mode before starting. All decisions go through a plan saved to `.harness/plans/` and require user approval before execution.

This command bootstraps the entire development harness in the target workspace. Follow every phase in order. Do not skip phases. Do not invent requirements -- ask when unsure.

---

## Phase 1: Inspect the Repo

Detect the following automatically. Do NOT ask the user for anything detectable from the repo.

### Auto-detect checklist

| What | How |
|------|-----|
| Languages | File extensions, config files (tsconfig.json, pyproject.toml, go.mod, Cargo.toml, etc.) |
| Frameworks | package.json dependencies, import patterns, config files (next.config.*, vite.config.*, etc.) |
| Package manager | Lock files (pnpm-lock.yaml, package-lock.json, yarn.lock, Pipfile.lock, poetry.lock) |
| Runtime | .node-version, .nvmrc, .python-version, .tool-versions, Dockerfile base images |
| Existing CI/CD | `.github/workflows/` directory and its contents |
| Existing tests | `tests/`, `__tests__/`, `*.test.*`, `*.spec.*`, test config files (jest.config.*, vitest.config.*, pytest.ini, etc.) |
| Existing deployment config | vercel.json, netlify.toml, fly.toml, Dockerfile, docker-compose.yml, serverless.yml, etc. |
| Git state | Current branch, default remote, remote URL |
| Installed Cursor skills | Check `~/.cursor/skills/` and `.cursor/skills/` for `commit-agent-changes` and `code-review` skills |

### Pre-existing artifact checks

| Artifact | Action if found |
|----------|----------------|
| `ROADMAP.md` | Note it exists; will use in Phase 3 |
| `.harness/` | **Warn the user.** Ask whether to reinitialize (wipes harness-owned files) or abort. If reinitializing, run `clear_harness.py` first to cleanly remove harness-owned artifacts. |
| `AGENTS.md` | Note it exists; will use managed-block insertion instead of creating a new file |
| `.cursor/rules/` | Note existing rules; harness rules will be added alongside them |
| `.cursor/hooks.json` | Note it exists; will merge the stop hook entry rather than overwriting |

Compile all findings into a detection summary. Present it to the user for confirmation before proceeding.

---

## Phase 2: Ask Questions

Organize questions by category. **Do NOT ask for anything already detected in Phase 1.** Only ask what cannot be inferred from the repo.

### Categories

**Product**
- What is this project's goal? (one sentence)
- Who are the target users?
- What are the success criteria? (measurable outcomes)

**Stack** (only undetected items)
- Any languages, frameworks, or tools not detected?
- Any external services (databases, auth providers, APIs)?

**Deployment**
- Deployment target (Vercel, AWS, GCP, Fly, Railway, etc.) -- skip if detected
- Production URL (or expected URL)
- Environments (e.g., preview + production)
- Smoke test URL or health endpoint for deployment verification
- Verification method (smoke-test-url, health-endpoint, deployed-e2e, or manual)

**Git Policy**
- Branch naming convention (e.g., `feature/ISSUE-123-short-description`)
- Commit convention (e.g., conventional-commits, freeform)
- Preferred PR size (small, medium, large)
- Merge strategy (squash, merge, rebase)
- Review policy (ai-review, human-review, both, none)

**Testing**
- E2E framework preference (Playwright, Cypress, or none) -- skip if detected
- Coverage targets (percentage or "best effort")

**Quality**
- Definition of done (list of conditions for a unit to be considered complete)
- Mandatory checks before marking work done (lint, test, build, e2e-smoke, etc.)

Present all questions in a single structured message. Wait for answers before proceeding.

---

## Phase 3: Generate ROADMAP.md

- If `ROADMAP.md` already exists in the repo root, read it and confirm with the user that it represents current product intent. Proceed to Phase 4.
- If no `ROADMAP.md` exists, help the user draft one:
  1. Ask the user to describe the major milestones or features they want to build
  2. Organize their input into a markdown document with `##` headings for each major milestone
  3. Include brief descriptions under each heading
  4. Write `ROADMAP.md` to the repo root
  5. Mark it as **product-owned** (the harness reads it but never modifies it after creation)

The ROADMAP is the source of product intent. Everything downstream flows from it.

---

## Phase 4: Compile Roadmap into Phases

### Step 1: Run the skeletonizer

Run `compile_roadmap.py` from the skill's `scripts/` directory:

```
python3 {SKILL_DIR}/scripts/compile_roadmap.py --roadmap ROADMAP.md --output .harness/phase-graph.json
```

This produces a **skeleton only** -- phase IDs, slugs, and empty unit arrays parsed from ROADMAP.md headings.

### Step 2: Interrogate and refine each phase

For each phase in the skeleton:

1. **Refine boundaries** -- Is this phase too broad? Too narrow? Should it be split or merged?
2. **Add units** -- Break the phase into bounded, validator-backed units of work. Each unit must have:
   - `id`: Unique identifier (e.g., `U-001`)
   - `description`: What the unit accomplishes
   - `acceptance criteria`: Concrete conditions for completion
   - `validation method`: How the validator proves completion (e.g., `pytest tests/unit/test_auth.py`, `npm run lint`, `curl -s https://app.example.com/api/health | grep ok`)
3. **Determine dependencies** -- Which phases must complete before this one can start?
4. **Attach validation gates** -- Which layers from the validation hierarchy (1-7) apply? Reference `references/validation-hierarchy.md`.
5. **Identify deployment implications** -- Does this phase affect deployment? If yes, layers 5+ are required.

### Step 3: Write phase documents

For each phase, create a `PHASES/PHASE_XXX_slug.md` file following the phase contract in `references/phase-contract.md`. Use the template from `templates/phase-template.md`.

Every phase document must include all required sections from the contract: Objective, Why This Phase Exists, Scope, Non-goals, Dependencies, User-visible Outcomes, Units of Work table, Validation Gates, Deployment Implications, Completion Evidence Required, Rollback/Failure Considerations, and Status.

### Step 4: Write phase-graph.json

Update `.harness/phase-graph.json` with the full dependency graph, all phases, all units, all statuses set to `pending`.

Present the compiled phase plan to the user for review. Adjust based on feedback before proceeding.

---

## Phase 5: Generate Harness Artifacts

Create every file listed below. Use schemas from `schemas/` and templates from `templates/` in this skill directory as references.

### .harness/ directory

| File | Content |
|------|---------|
| `config.json` | Populate from Phase 1 detection + Phase 2 answers. Follow `schemas/config.json` structure. Include `schema_version`, `skill_version`, `project`, `stack`, `deployment`, `git`, `testing`, `quality`, and `execution_mode` fields. |
| `manifest.json` | List ALL generated files with correct ownership classes. CI/CD scaffolding and E2E scaffolding are **product-owned**. Everything else the harness creates is **harness-owned**. Pre-existing files that get managed blocks are **managed-block**. Follow `schemas/manifest.json` structure. |
| `state.json` | Initial state with first active phase and first unit. Follow `schemas/state.json` structure. Set `session_count: 0`, `loop_budget: 10`, empty issues and drift. |
| `phase-graph.json` | Already generated in Phase 4. Verify it is in place. |
| `checkpoint.md` | Initial checkpoint from `templates/checkpoint-template.md`. Fill in: last completed = "Harness created", next = first unit description, no blockers, no evidence yet. |
| `ARCHITECTURE.md` | Generate from `references/architecture.md`, adapted to this specific project. Replace generic references with project-specific paths, stack names, and conventions. |
| `plans/` | Create empty directory. |
| `issues/` | Create empty directory. |
| `.gitignore` | Contains `.invoke-active` — the transient session flag must not be committed. |
| `scripts/` | Copy ALL Python scripts from this skill's `scripts/` directory: `compile_roadmap.py`, `validate_harness.py`, `select_next_unit.py`, `sync_harness.py`, `clear_harness.py`, `normalize_issues.py`, `harness_utils.py`. |

### .cursor/commands/ -- workspace slash commands

Generate 7 workspace command files. Each file must:

1. State its purpose in a one-line comment at the top
2. Tell the agent to read `.harness/ARCHITECTURE.md` for context
3. Contain the full workflow steps (self-contained, no references to the global skill)
4. Reference `.harness/scripts/` for deterministic operations
5. Reference `.harness/state.json`, `.harness/phase-graph.json`, etc. for data

Use the templates from this skill's `templates/workspace-commands/` directory. The 7 commands are:

| Workspace Command File | Purpose |
|----------------------|---------|
| `create-development-harness.md` | Rebuild or reinitialize the harness |
| `invoke-development-harness.md` | Execute the next unit of work |
| `update-development-harness.md` | Modify harness configuration or phase plan |
| `harness-state.md` | Report current harness and project state |
| `sync-development-harness.md` | Sync harness with code reality |
| `clear-development-harness.md` | Remove all harness artifacts |
| `inject-harness-issues.md` | Report problems or inject issues |

### .cursor/hooks.json

Generate the hooks configuration:

```json
{
  "version": 1,
  "hooks": {
    "stop": [
      {
        "command": "python3 .cursor/hooks/continue-loop.py"
      }
    ]
  }
}
```

**If `.cursor/hooks.json` already exists**, read it, parse the JSON, and MERGE the stop hook entry into the existing `hooks.stop` array. Do not overwrite other hooks. Do not duplicate the entry if it already exists.

### .cursor/hooks/continue-loop.py

Copy from this skill's `templates/hooks/continue-loop.py`.

### .cursor/rules/ -- harness rule files

Generate from the corresponding templates in this skill's `templates/rules/` directory:

| Rule File | Source Template |
|-----------|---------------|
| `harness-core.mdc` | `templates/rules/harness-core.mdc` |
| `harness-validation.mdc` | `templates/rules/harness-validation.mdc` |
| `harness-git.mdc` | `templates/rules/harness-git.mdc` -- customize with project's git policy from config |
| `harness-deployment.mdc` | `templates/rules/harness-deployment.mdc` |
| `harness-testing.mdc` | `templates/rules/harness-testing.mdc` |

### .harness/pr-review-checklist.md

Copy from `templates/rules/pr-review-checklist.md`. This is used by the invoke command's phase completion review step. Add to manifest as harness-owned.

### PHASES/ directory

Already generated in Phase 4. Verify all phase documents are in place.

### AGENTS.md

- **If no `AGENTS.md` exists:** Create a new one (harness-owned). Include harness overview, pointer to `.harness/ARCHITECTURE.md`, list of available workspace commands, and key rules.
- **If `AGENTS.md` already exists:** Insert a managed block using markers:
  ```
  <!-- HARNESS:START -->
  ... harness content ...
  <!-- HARNESS:END -->
  ```
  Track as `managed-block` in manifest with `marker_pattern: "HARNESS:START/HARNESS:END"`.

---

## Phase 6: Scaffold CI/CD and E2E (if missing)

### CI/CD

If no `.github/workflows/` directory exists:

1. Scaffold a basic CI workflow appropriate to the detected stack (e.g., Node: install + lint + test + build; Python: install + lint + test)
2. Name it `.github/workflows/ci.yml`
3. Include steps for all mandatory checks from config
4. Mark as **product-owned** in manifest

If CI/CD already exists, skip this step entirely.

### E2E Tests

If no E2E tests exist and an E2E framework is configured:

1. Scaffold a baseline E2E test file appropriate to the framework (e.g., Playwright: `tests/e2e/smoke.spec.ts`; Cypress: `cypress/e2e/smoke.cy.ts`)
2. Include a minimal smoke test that verifies the app loads
3. Mark as **product-owned** in manifest

If E2E tests already exist, skip this step entirely.

**All scaffolded files are product-owned.** The harness creates them as a convenience; the project owns them immediately.

---

## Phase 7: Validate and Report

### Validate

Run `validate_harness.py` from `.harness/scripts/`:

```
python3 .harness/scripts/validate_harness.py --root .
```

If validation fails, fix the errors and re-run until it passes. Do not proceed with errors.

### Set active state

Update `.harness/state.json`:
- Set `active_phase` to the first phase ID
- Set `active_unit` to the first unit ID in that phase
- Set `next_unit` to the second unit ID (or null if only one unit)

Update `.harness/phase-graph.json`:
- Set the first phase status to `in_progress`
- Set the first unit status to `pending` (it will become `in_progress` on first invoke)

### Report

Output a summary to the user covering:

1. **Files created** -- full list with ownership class
2. **Active phase** -- ID, slug, objective
3. **First unit** -- ID, description, validation method
4. **Open questions** -- anything unresolved from Q&A
5. **Risks** -- anything detected that might cause problems (missing deploy config, no CI, etc.)
6. **Installed skills** -- which Cursor skills were detected and how they integrate (commit-agent-changes for git commits, code-review for PR reviews)
7. **Next step** -- tell the user to run `/invoke-development-harness` to begin execution
