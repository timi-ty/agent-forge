# cursor-skills

Portable collection of [Cursor](https://cursor.com) agent skills. Clone this repo to install battle-tested skills on any machine -- globally or per-workspace.

## Skill Catalog

| Skill | Description | Triggers | Dependencies |
|-------|-------------|----------|--------------|
| **[code-review](skills/code-review/)** | Senior-engineer PR code review. Checks conformance, correctness, efficiency, and dead code across an 8-phase workflow. | `review a PR`, `code review`, `review pull request`, attach a PR URL | `gh` CLI |
| **[commit-agent-changes](skills/commit-agent-changes/)** | Turn the current agent session's changes into a branch with logically grouped commits and a PR. | `commit my changes`, `commit agent changes`, `create a PR from this session`, `push what you changed` | `gh` CLI, `git` |
| **[redeploy-frontend](skills/redeploy-frontend/)** | Trigger a Vercel redeploy by pushing a timestamp comment. Auto-detects package manager, branch, and target file. Auto-fixes prettier issues. | `redeploy`, `redeploy frontend`, `trigger vercel deploy` | `git`, Vercel |
| **[sync-skills](skills/sync-skills/)** | Sync locally installed skills to match a branch of this repo. Handles first-time installs and updates in one flow. | paste a `github.com/timi-ty/cursor-skills` URL, `install skills`, `update skills`, `sync skills` | `gh` CLI, `git` |

## Installation

### Via Cursor agent (recommended)

Once `sync-skills` is installed, all future installs and updates are agent-driven: paste the repo URL (or a branch URL) into any Cursor agent chat and the `sync-skills` skill handles the rest — diffing, confirming, and applying changes across global and workspace scopes.

For the **first-time bootstrap** (before `sync-skills` is available), use one of the manual methods below.

### Quick install (bootstrap)

```bash
# Clone the repo
git clone https://github.com/timi-ty/cursor-skills.git
cd cursor-skills

# Install a skill globally (available in all projects)
./install.sh sync-skills --global

# Then paste https://github.com/timi-ty/cursor-skills into Cursor agent chat
# to install the rest of the skills via the sync-skills skill
```

### Manual install

1. Clone or download this repo.
2. Copy the desired skill folder into the target location:

```bash
# Global (all projects on this machine)
cp -r skills/code-review ~/.cursor/skills/code-review

# Workspace-local (current project only)
cp -r skills/code-review .cursor/skills/code-review
```

3. Restart Cursor or open a new agent session. The skill is now available.

### Install all skills at once

```bash
./install.sh --all --global      # every skill, globally
./install.sh --all --workspace   # every skill, current workspace
```

## For AI Agents

> **If you are an AI agent** (Cursor, Claude, Copilot, or any LLM-based coding assistant) and a user points you to this repo, follow the instructions below to find and install the right skill.

### Step 1 -- Find a matching skill

Fetch and parse [`catalog.json`](catalog.json) at the repo root. It contains a structured list of every skill with:

- `name` -- unique skill identifier
- `description` -- what the skill does
- `triggers` -- phrases and scenarios that indicate this skill is needed
- `path` -- folder path relative to the repo root
- `files` -- list of files in the skill folder
- `dependencies` -- external tools the skill requires
- `notes` -- additional context (workflow summary, caveats)

Match the user's request against `triggers` and `description`. If multiple skills match, present them and let the user choose.

### Step 2 -- Ask the user where to install

Before copying any files, ask the user:

1. **Scope**: Install globally (`~/.cursor/skills/`) or workspace-locally (`.cursor/skills/`)?
   - Global = available in every project on this machine.
   - Workspace = available only in the current project, and version-controlled with the repo.
2. **Confirmation**: Show the skill name, description, and dependencies. Confirm they want to proceed.

### Step 3 -- Install the skill

1. If the repo is not already cloned locally, clone it to a temporary location or fetch the specific skill folder.
2. Copy the entire skill folder to the chosen destination:

```bash
# Global
cp -r <repo>/skills/<skill-name> ~/.cursor/skills/<skill-name>

# Workspace
mkdir -p .cursor/skills
cp -r <repo>/skills/<skill-name> .cursor/skills/<skill-name>
```

3. Verify the `SKILL.md` file exists at the destination.

### Step 4 -- Verify and report

Tell the user:
- Which skill was installed and where.
- Any dependencies they need to have available (e.g., `gh` CLI).
- That they may need to start a new Cursor agent session for the skill to be picked up.

### Platform notes

| OS | Global skills path |
|----|-------------------|
| macOS / Linux | `~/.cursor/skills/` |
| Windows | `%USERPROFILE%\.cursor\skills\` |

## Skill anatomy

Each skill is a folder containing a `SKILL.md` file with YAML frontmatter:

```
skill-name/
├── SKILL.md          # Required -- main instructions with name + description frontmatter
├── checklist.md      # Optional -- supporting reference material
└── scripts/          # Optional -- utility scripts
```

The `SKILL.md` frontmatter tells Cursor when to activate the skill:

```yaml
---
name: skill-name
description: What this skill does and when to use it.
---
```

## Contributing

To add a new skill:

1. Create a folder under `skills/` with your skill name (lowercase, hyphens).
2. Add a `SKILL.md` with the required frontmatter (`name`, `description`) and instructions.
3. Add an entry to `catalog.json` with all metadata fields.
4. Update the catalog table in this README.
5. Open a PR.

## License

MIT
