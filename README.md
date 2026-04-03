# agent-forge

Portable collection of AI agent skills and a development harness for AI-native engineering. Works with both [Cursor](https://cursor.com) and [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Paste the repo URL into an agent chat to install battle-tested skills on any machine -- globally or per-workspace.

## Skill Catalog

| Skill | Description | Triggers | Dependencies |
|-------|-------------|----------|--------------|
| **[development-harness](skills/development-harness/)** | Project-local control plane that compiles ROADMAP.md into phased, validator-backed autonomous execution. 7 commands: create, invoke, update, state, sync, clear, inject-issues. | `create development harness`, `invoke harness`, `continue from harness`, `update harness`, `harness state`, `sync harness`, `clear harness`, `inject issues` | `git`, `python3` |
| **[code-review](skills/code-review/)** | Senior-engineer PR code review. Checks conformance, correctness, efficiency, and dead code across an 8-phase workflow. | `review a PR`, `code review`, `review pull request`, attach a PR URL | `gh` CLI |
| **[commit-agent-changes](skills/commit-agent-changes/)** | Turn the current agent session's changes into logically grouped commits on a remote-only branch with a PR, without ever leaving the base branch. | `commit my changes`, `commit agent changes`, `create a PR from this session`, `push what you changed` | `gh` CLI, `git` |
| **[issue-resolution-report](skills/issue-resolution-report/)** | Write and post a technically sound issue resolution report as a GitHub issue comment and/or PR description after fixing a bug. | `write a resolution report`, `document what was fixed`, `update a PR body with findings`, `post a resolution comment` | `gh` CLI |
| **[aws](skills/aws/)** | AWS CLI operations with safety rails. Confirms destructive ops, warns about costs, covers EC2/S3/IAM/Lambda/CloudFormation/RDS and more. | `AWS CLI`, `manage AWS`, `EC2 instances`, `S3 bucket`, `deploy to AWS` | AWS CLI v2 |
| **[redeploy-frontend](skills/redeploy-frontend/)** | Trigger a Vercel redeploy by pushing a timestamp comment. Auto-detects package manager, branch, and target file. Auto-fixes prettier issues. | `redeploy`, `redeploy frontend`, `trigger vercel deploy` | `git`, Vercel |
| **[playwright-pool](skills/playwright-pool/)** | Playwright browser pool for multi-agent automation. Installs a pooling MCP proxy so multiple agents each get an isolated browser session — no contention, no shared state. Claude Code only. | `set up playwright pool`, `install playwright pool`, `browser pool`, `multi-agent browser automation` | `node.js >= 18`, `@playwright/mcp` (via npx) |
| **[sync-skills](skills/sync-skills/)** | Sync locally installed skills to match a branch of this repo. Handles first-time installs and updates in one flow. | paste a `github.com/timi-ty/cursor-forge` URL, `install skills`, `update skills`, `sync skills` | `gh` CLI, `git` |
| **[btw](skills/btw/)** | Interrupt the current task with a side-task that runs in a background subagent. | `/btw`, `btw`, `by the way` | — |

## Development Harness

The development harness is a project-local control plane that turns a ROADMAP.md into a sequence of validated, self-executing tasks.

**Workflow:**
1. Install the skill globally: `./install.sh development-harness --global`
2. In any project, say "create development harness" -- the agent asks questions, reads your ROADMAP.md, and generates the full harness
3. After creation, 7 slash commands are available in your workspace (`/invoke-development-harness`, `/harness-state`, etc.)
4. Run `/invoke-development-harness` to execute work -- a stop hook keeps the agent iterating until a goal is verified or ambiguity is hit
5. Use `/inject-harness-issues` to report problems, `/sync-development-harness` to reconcile state, `/harness-state` for reports

**Architecture:** One globally-installed skill bootstraps workspace-local commands, hooks, rules, and deterministic Python helpers. All scripts use stdlib only -- no pip dependencies. See [skills/development-harness/references/architecture.md](skills/development-harness/references/architecture.md) for full details.

## Installation

### Via Cursor agent (recommended)

Paste `https://github.com/timi-ty/cursor-forge` (or a branch URL) into any Cursor agent chat. The agent reads the repo's `catalog.json`, presents available skills, asks where to install them, and copies them into place. This works for both first-time installs and subsequent updates.

If the `sync-skills` skill is already installed locally, the agent uses it for smarter syncing -- diffing changed files, detecting removals, and batch-updating across scopes. Otherwise, the agent follows the repo's built-in [AI instructions](#for-ai-agents) to install from scratch. Either way, the entry point is the same: paste the URL.

### Via Claude Code (recommended)

Paste `https://github.com/timi-ty/cursor-forge` into any Claude Code session. The agent reads `catalog.json`, presents available skills, asks where to install them, and copies them into place.

Skills are installed to `~/.claude/commands/<skill-name>/` (global) or `.claude/commands/<skill-name>/` (workspace-local). The workflow is identical to the Cursor flow.

### Manual install

1. Clone or download this repo.
2. Copy the desired skill folder into the target location:

**Cursor:**
```bash
# Global (all projects on this machine)
cp -r skills/code-review ~/.cursor/skills/code-review

# Workspace-local (current project only)
cp -r skills/code-review .cursor/skills/code-review
```

**Claude Code:**
```bash
# Global (all projects on this machine)
cp -r skills/code-review ~/.claude/commands/code-review

# Workspace-local (current project only)
cp -r skills/code-review .claude/commands/code-review
```

3. Restart the agent or open a new session. The skill is now available.

To install everything at once:

```bash
./install.sh --all --global                    # Cursor, globally (default)
./install.sh --all --workspace                 # Cursor, workspace-local
./install.sh --all --global --tool claude-code  # Claude Code, globally
```

## For AI Agents

> **If you are an AI agent** (Cursor, Claude Code, Copilot, or any LLM-based coding assistant) and a user points you to this repo, follow the instructions below to find and install the right skill.

### Step 0 -- Detect the host tool

Determine whether you are running in **Cursor** or **Claude Code**:

- If your system prompt identifies you as Claude Code, or you have access to the `AskUserQuestion` tool (not `AskQuestion`), use **Claude Code** paths.
- Otherwise, use **Cursor** paths.

Set `$TOOL` to `cursor` or `claude-code` for use in all subsequent steps.

### Step 1 -- Find a matching skill

Fetch and parse [`catalog.json`](catalog.json) at the repo root. It contains a structured list of every skill with:

- `name` -- unique skill identifier
- `description` -- what the skill does
- `triggers` -- phrases and scenarios that indicate this skill is needed
- `path` -- folder path relative to the repo root
- `files` -- list of files in the skill folder
- `dependencies` -- external tools the skill requires
- `notes` -- additional context (workflow summary, caveats)
- `platforms` -- tool-specific install paths for `cursor` and `claude-code`

Match the user's request against `triggers` and `description`. If multiple skills match, present them and let the user choose.

### Step 2 -- Ask the user where to install

Before copying any files, ask the user:

1. **Scope**: Install globally or workspace-locally?
   - Global = available in every project on this machine.
   - Workspace = available only in the current project, and version-controlled with the repo.
2. **Confirmation**: Show the skill name, description, and dependencies. Confirm they want to proceed.

### Step 3 -- Install the skill

1. If the repo is not already cloned locally, clone it to a temporary location or fetch the specific skill folder.
2. Copy the entire skill folder to the chosen destination using the paths from `catalog.json` `platforms.$TOOL`:

```bash
# Global
cp -r <repo>/skills/<skill-name> <platforms.$TOOL.install_path_global>

# Workspace
mkdir -p <parent-of-workspace-path>
cp -r <repo>/skills/<skill-name> <platforms.$TOOL.install_path_workspace>
```

3. Verify the `SKILL.md` file exists at the destination.

### Step 4 -- Verify and report

Tell the user:
- Which skill was installed and where.
- Any dependencies they need to have available (e.g., `gh` CLI).
- That they may need to start a new agent session for the skill to be picked up.

### Platform notes

| Tool | OS | Global path | Workspace path |
|------|----|-------------|----------------|
| Cursor | macOS / Linux | `~/.cursor/skills/` | `.cursor/skills/` |
| Cursor | Windows | `%USERPROFILE%\.cursor\skills\` | `.cursor\skills\` |
| Claude Code | macOS / Linux | `~/.claude/commands/` | `.claude/commands/` |
| Claude Code | Windows | `%USERPROFILE%\.claude\commands\` | `.claude\commands\` |

## Skill anatomy

Each skill is a folder containing a `SKILL.md` file with YAML frontmatter:

```
skill-name/
├── SKILL.md          # Required -- main instructions with name + description frontmatter
├── checklist.md      # Optional -- supporting reference material
└── scripts/          # Optional -- utility scripts
```

The `SKILL.md` frontmatter tells the agent when to activate the skill:

```yaml
---
name: skill-name
description: What this skill does and when to use it.
---
```

Both Cursor and Claude Code discover skills by reading `SKILL.md` files from their respective skill/command directories.

## Contributing

To add a new skill:

1. Create a folder under `skills/` with your skill name (lowercase, hyphens).
2. Add a `SKILL.md` with the required frontmatter (`name`, `description`) and instructions.
3. Add an entry to `catalog.json` with all metadata fields, including `platforms` for both Cursor and Claude Code.
4. Update the catalog table in this README.
5. Open a PR.

## License

MIT
