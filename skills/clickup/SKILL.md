---
name: clickup
description: Set up ClickUp integration for AI coding agents. Provisions credentials, links a ClickUp view to the current project, and provides direct API query tools for fetching tasks, comments, and attachments. Works with both Cursor and Claude Code. TRIGGER on "set up clickup", "configure clickup", "link clickup", "connect clickup", "clickup setup". Also handles sub-commands: "change clickup view", "reconfigure clickup", "remove clickup from this project".
---

# ClickUp Integration

Connects your AI coding agent to ClickUp so you can query tasks, comments, and attachments directly from the IDE during development — no need to open ClickUp at all. Works with both Cursor and Claude Code.

**How it works once set up:**
- A local query helper provides direct ClickUp API access
- You give the agent a task reference (e.g. "work on PROJ-123" or "what's left in this sprint")
- The agent calls the query helper to fetch tasks from the linked view, inspect individual tasks, read comments, and download attachments
- No MCP server, no external dependencies — just Node.js and the ClickUp REST API v2

---

## Dispatch

Read the user's intent and jump to the appropriate section:

| User says | Go to |
|-----------|-------|
| "set up clickup", "configure clickup", "clickup setup", "connect clickup", "link clickup view" | **SETUP** |
| "change clickup view", "link a different view" | **CHANGE VIEW** |
| "reconfigure clickup", "update clickup token", "refresh clickup credentials" | **RECONFIGURE** |
| "remove clickup from this project", "unlink clickup" | **REMOVE VIEW** |

---

## SETUP

Run this full flow when the user invokes the skill without a more specific intent.

---

### Step 0: Detect platform and resolve paths

**Detect the host tool:**

- **Cursor**: Your system prompt identifies you as a Cursor agent, or you have access to the `AskQuestion` tool.
- **Claude Code**: Your system prompt identifies you as Claude Code, or you have access to the `AskUserQuestion` tool.

Set `$TOOL` to `cursor` or `claude-code`.

**Resolve the skill install path:**

```bash
node -p "require('os').homedir()"
```

Set `$NATIVE_HOME` to the output.

Set paths based on `$TOOL`:

| Variable | Cursor | Claude Code |
|----------|--------|-------------|
| `$SKILL_DIR` | `$NATIVE_HOME/.cursor/skills/clickup` | `$NATIVE_HOME/.claude/commands/clickup` |
| `$CLICKUP_ENV_FILE` | `$NATIVE_HOME/.clickup/.env` | `$NATIVE_HOME/.clickup/.env` |
| `$SETUP_SCRIPT` | `$SKILL_DIR/setup/index.mjs` | `$SKILL_DIR/setup/index.mjs` |
| `$QUERY_SCRIPT` | `$SKILL_DIR/query/index.mjs` | `$SKILL_DIR/query/index.mjs` |

Also check the workspace-local path (`.cursor/skills/clickup` or `.claude/commands/clickup`). If the skill exists there, prefer it over the global path.

**Resolve the project root:**

```bash
git rev-parse --show-toplevel
```

If this fails: "Could not find a git repository root. Please run this from inside a git project." Then stop.

Set `$PROJECT_ROOT` to the output.

---

### Step 1: Provision ClickUp API token

**Check for existing token:**

```bash
node -e "
const fs = require('fs');
const p = process.argv[1];
if (!fs.existsSync(p)) { console.log('MISSING'); process.exit(0); }
const content = fs.readFileSync(p, 'utf8');
const match = content.match(/^CLICKUP_API_TOKEN=(.+)$/m);
console.log(match ? match[1].trim() : 'MISSING');
" "$CLICKUP_ENV_FILE"
```

If output is not `MISSING`, set `$CLICKUP_TOKEN` to the value and skip to the **[Validate]** check.

**If MISSING — ask the user:**

> "To connect to ClickUp, I need your Personal API Token.
>
> Generate one at: **ClickUp avatar (upper-right) → Settings → Apps → Generate** (under API Token)
>
> Paste your token:"

Set `$CLICKUP_TOKEN` to the user's input.

**[Validate]** — call the ClickUp API to confirm the token works:

```bash
node "$SETUP_SCRIPT" validate-token "$CLICKUP_TOKEN"
```

Parse the JSON output:
- If `ok: true`: print `Authenticated as {name} ({email})`. Continue.
- If `ok: false`: show the error message and re-ask. Retry up to 3 times. If all fail, stop.

**Save token to `$CLICKUP_ENV_FILE`:**

```bash
node -e "
const fs = require('fs'), path = require('path');
const envFile = process.argv[1];
const token = process.argv[2];
fs.mkdirSync(path.dirname(envFile), { recursive: true });
let content = '';
try { content = fs.readFileSync(envFile, 'utf8'); } catch {}
if (content.includes('CLICKUP_API_TOKEN=')) {
  content = content.replace(/^CLICKUP_API_TOKEN=.+$/m, 'CLICKUP_API_TOKEN=' + token);
} else {
  content = content.trimEnd();
  content = (content ? content + '\n' : '') + 'CLICKUP_API_TOKEN=' + token + '\n';
}
fs.writeFileSync(envFile, content);
console.log('saved');
" "$CLICKUP_ENV_FILE" "$CLICKUP_TOKEN"
```

---

### Step 2: Link a ClickUp view

Ask the user:

> "Paste your ClickUp URL. This can be:
> - A **view URL** (e.g. `app.clickup.com/9014734012/v/l/8cn3v5w-634`) — links directly
> - A **workspace URL** (e.g. `app.clickup.com/9014734012`) — lets you browse and pick a view"

**Parse the URL:**

```bash
node "$SETUP_SCRIPT" parse-url "<pasted_url>"
```

**If `type: "view"`:**
- Set `$CHOSEN_TEAM_ID` from `teamId` and `$CHOSEN_VIEW_ID` from `viewId`.
- Verify the view is accessible:
  ```bash
  node "$SETUP_SCRIPT" validate-view "$CHOSEN_VIEW_ID" "$CLICKUP_TOKEN"
  ```
- If ok: print `View accessible ({taskCount} tasks found)`. Skip to **Step 3**.
- If error: show error, re-ask.

**If `type: "workspace"`:**
- Set `$CHOSEN_TEAM_ID` from `teamId`.
- Enumerate views:
  ```bash
  node "$SETUP_SCRIPT" get-views "$CHOSEN_TEAM_ID" "$CLICKUP_TOKEN"
  ```
- Format a numbered list grouped by space and folder:
  ```
    [Space Name]
      [Folder Name]
        1. View Name (list: List Name, type: list)
        2. Another View (list: Other List, type: board)
      (no folder)
        3. Direct View (list: Folderless List, type: list)
  ```
- Ask: "Which view should I link to this project? Enter a number (or Q to quit):"
- Set `$CHOSEN_VIEW_ID` from the selection.

**If `type: "task"`:**
- Print: "That looks like a task URL. I need a **view URL** to link to this project. Open the view you want, then paste its URL."
- Re-ask.

**If `ok: false`:** Show error, re-ask.

---

### Step 3: Write configuration to CLAUDE.md

Check if `$PROJECT_ROOT/CLAUDE.md` exists. Read it if so.

**If a `## ClickUp` section already exists:**
Extract the current Team ID and View ID.
Ask: "This project already has a ClickUp view linked (View `{current view ID}`). Replace with `{CHOSEN_VIEW_ID}`? (y/N)"
If N: stop.

**Write or update the section:**

If CLAUDE.md does not exist, create it with:
```markdown
## ClickUp
Team ID: `{CHOSEN_TEAM_ID}`
View ID: `{CHOSEN_VIEW_ID}`
```

If CLAUDE.md exists but has no `## ClickUp` section, append:
```markdown

## ClickUp
Team ID: `{CHOSEN_TEAM_ID}`
View ID: `{CHOSEN_VIEW_ID}`
```

If CLAUDE.md exists and has a `## ClickUp` section, replace the `Team ID:` and `View ID:` lines with the new values.

---

### Step 4: Done

Print:

```
ClickUp is configured for this project.

    Team ID:     {CHOSEN_TEAM_ID}
    View ID:     {CHOSEN_VIEW_ID}
    Credentials: {CLICKUP_ENV_FILE}
    Query tool:  {QUERY_SCRIPT}

From now on, when you reference tasks or ask about project state,
I will automatically query ClickUp to get accurate, up-to-date information.
```

---

## CHANGE VIEW

Use when the user wants to link a different ClickUp view without touching credentials.

1. Resolve paths (Step 0).
2. Read `$CLICKUP_TOKEN` from `$CLICKUP_ENV_FILE`. If missing, redirect to **SETUP**.
3. Ask: "Paste a ClickUp view URL, or a workspace URL to browse views:"
   - If they paste a view URL: parse with `parse-url`, follow the view branch from Step 2.
   - If they paste a workspace URL: parse, run `get-views`, present the picker.
4. Run **Step 3** (write config to CLAUDE.md).
5. Print confirmation.

---

## RECONFIGURE

Use when the user wants to re-enter credentials.

1. Resolve paths (Step 0).
2. Ask: "What do you want to reconfigure? (1) API token, (2) Both token and view"
3. Based on choice: run Step 1 and/or Step 2, forcing the prompts even if values exist.
4. Print confirmation. No restart needed — the query helper reads credentials fresh on every call.

---

## REMOVE VIEW

Remove the ClickUp association from the current project's CLAUDE.md.

1. Resolve `$PROJECT_ROOT`.
2. Read `$PROJECT_ROOT/CLAUDE.md`. If no `## ClickUp` section exists, print "No ClickUp view is linked to this project." and stop.
3. Extract and show the current view ID.
4. Ask: "Remove the ClickUp association from this project? Global credentials are kept. (y/N)"
5. If y: remove the entire `## ClickUp` section from CLAUDE.md. Print confirmation.

---

## How to use ClickUp during development

Once set up, use this workflow whenever you need to understand, reference, or act on project tasks.
Do this **proactively** — if the project has ClickUp config in CLAUDE.md and the user
references a task, ticket, or asks about project state, always query ClickUp first without being asked.

### Query helper

All ClickUp data is fetched via the query helper:

```bash
node "$QUERY_SCRIPT" <command> [args...]
```

Where `$QUERY_SCRIPT` is the path resolved in Step 0:
- **Cursor**: `~/.cursor/skills/clickup/query/index.mjs`
- **Claude Code**: `~/.claude/commands/clickup/query/index.mjs`

The helper automatically reads the API token from `~/.clickup/.env` and the Team/View IDs
from the nearest CLAUDE.md. All output is JSON on stdout.

### Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `tasks` | `tasks [--status X] [--assignee X] [--fresh]` | List tasks in the linked view. Cached for 5 min. `--status` and `--assignee` filter client-side. |
| `task` | `task <task_id>` | Full details for a single task: description, status, dates, assignees, custom fields, subtasks, attachments, checklists. |
| `comments` | `comments <task_id>` | Comment thread with author and timestamps. |
| `search` | `search <query>` | Search tasks by name across the workspace (client-side filtering, up to 300 tasks scanned). |
| `download-attachment` | `download-attachment <url> <path>` | Download an attachment to a local path (sends auth for private-link workspaces). |
| `statuses` | `statuses` | Available statuses for the linked list — useful for understanding task state vocabulary. |

### Recommended workflow

1. **Overview**: `tasks` to see all tasks in the linked view with their statuses and assignees.
2. **Filter**: `tasks --status "in progress"` or `tasks --assignee "John"` to narrow down.
3. **Inspect**: `task <task_id>` to read the full description, acceptance criteria, and context.
4. **Context**: `comments <task_id>` to read the discussion thread for additional context.
5. **Find**: `search <query>` when the user references a task not in the current view.
6. **Assets**: `download-attachment <url> <path>` for any attached images or files.
7. **Vocabulary**: `statuses` to understand what states are available before discussing task transitions.

### When to query proactively

- User says "work on PROJ-123" → call `task` to understand the requirement before coding.
- User says "what's left in the sprint" → call `tasks` to show current state.
- User says "check the comments on that task" → call `comments`.
- User pastes a ClickUp URL containing a task ID → extract and call `task`.
- User asks about project status, blockers, or priorities → call `tasks` with relevant filters.

### Attachment downloads

ClickUp attachment URLs are publicly accessible by default, but workspaces can enable
"Private Attachment Links" which makes them auth-gated. The `download-attachment` command
always sends the API token, so it works in both cases. Use it for images, PDFs, and any
other files attached to tasks.

### Rate limiting

The helper retries automatically on 429 with exponential backoff (up to 3 retries).
If ClickUp returns a wait longer than 60 seconds, it fails fast with an actionable error message.
ClickUp's rate limit is 100 requests per minute per token.

### Cache behavior

The `tasks` command caches view results for 5 minutes (tasks change state frequently).
Use `--fresh` to bypass the cache. All other commands are uncached and always fetch live data.

### Example

```bash
# Resolve the query script path for your platform first (see Step 0)
Q="$QUERY_SCRIPT"

# 1. See all tasks in the view
node "$Q" tasks

# 2. Filter by status
node "$Q" tasks --status "in progress"

# 3. Get full task details
node "$Q" task "abc123"

# 4. Read comments
node "$Q" comments "abc123"

# 5. Search across workspace
node "$Q" search "billing page"

# 6. Download an attachment
node "$Q" download-attachment "https://t.clickup.com/..." "./assets/mockup.png"

# 7. Check available statuses
node "$Q" statuses
```
