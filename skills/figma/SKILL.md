---
name: figma
description: Set up Figma integration for AI coding agents. Provisions credentials, links a Figma file to the current project, and provides direct API query tools for fetching design specs and images. Works with both Cursor and Claude Code. TRIGGER on "set up figma", "configure figma", "link figma", "connect figma", "figma setup". Also handles sub-commands: "change figma file", "reconfigure figma", "remove figma from this project".
---

# Figma Integration

Connects your AI coding agent to Figma so you can query designs directly from the IDE during frontend development — no need to open Figma at all. Works with both Cursor and Claude Code.

**How it works once set up:**
- A local query helper provides direct Figma API access
- You give the agent a task (e.g. "implement the consumer billing page")
- The agent calls the query helper to browse the file structure, find the matching frame, fetch full design specs, and generate code from them
- No MCP server, no external dependencies — just Node.js and the Figma REST API

---

## Dispatch

Read the user's intent and jump to the appropriate section:

| User says | Go to |
|-----------|-------|
| "set up figma", "configure figma", "figma setup", "connect figma", "link figma file" | **SETUP** |
| "change figma file", "link a different file" | **CHANGE FILE** |
| "reconfigure figma", "update figma token", "refresh figma credentials" | **RECONFIGURE** |
| "remove figma from this project", "unlink figma" | **REMOVE FILE** |

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
| `$SKILL_DIR` | `$NATIVE_HOME/.cursor/skills/figma` | `$NATIVE_HOME/.claude/commands/figma` |
| `$FIGMA_ENV_FILE` | `$NATIVE_HOME/.figma/.env` | `$NATIVE_HOME/.figma/.env` |
| `$SETUP_SCRIPT` | `$SKILL_DIR/setup/index.mjs` | `$SKILL_DIR/setup/index.mjs` |
| `$QUERY_SCRIPT` | `$SKILL_DIR/query/index.mjs` | `$SKILL_DIR/query/index.mjs` |

Also check the workspace-local path (`.cursor/skills/figma` or `.claude/commands/figma`). If the skill exists there, prefer it over the global path.

**Resolve the project root:**

```bash
git rev-parse --show-toplevel
```

If this fails: "Could not find a git repository root. Please run this from inside a git project." Then stop.

Set `$PROJECT_ROOT` to the output.

---

### Step 1: Provision Figma API token

**Check for existing token:**

```bash
node -e "
const fs = require('fs');
const p = process.argv[1];
if (!fs.existsSync(p)) { console.log('MISSING'); process.exit(0); }
const content = fs.readFileSync(p, 'utf8');
const match = content.match(/^FIGMA_API_KEY=(.+)$/m);
console.log(match ? match[1].trim() : 'MISSING');
" "$FIGMA_ENV_FILE"
```

If output is not `MISSING`, set `$FIGMA_PAT` to the value and skip to the **[Validate]** check.

**If MISSING — ask the user:**

> "To connect to Figma, I need your Personal Access Token.
>
> Create one at: Figma > Settings > Security > Personal access tokens
> Required scopes: **File content** (read), **File metadata** (read)
>
> Paste your token:"

Set `$FIGMA_PAT` to the user's input.

**[Validate]** — call the Figma API to confirm the token works:

```bash
node "$SETUP_SCRIPT" validate-pat "$FIGMA_PAT"
```

Parse the JSON output:
- If `ok: true`: print `Authenticated as {name} ({email})`. Continue.
- If `ok: false`: show the error message and re-ask. Retry up to 3 times. If all fail, stop.

**Save token to `$FIGMA_ENV_FILE`:**

```bash
node -e "
const fs = require('fs'), path = require('path');
const envFile = process.argv[1];
const key = process.argv[2];
fs.mkdirSync(path.dirname(envFile), { recursive: true });
let content = '';
try { content = fs.readFileSync(envFile, 'utf8'); } catch {}
if (content.includes('FIGMA_API_KEY=')) {
  content = content.replace(/^FIGMA_API_KEY=.+$/m, 'FIGMA_API_KEY=' + key);
} else {
  content = content.trimEnd();
  content = (content ? content + '\n' : '') + 'FIGMA_API_KEY=' + key + '\n';
}
fs.writeFileSync(envFile, content);
console.log('saved');
" "$FIGMA_ENV_FILE" "$FIGMA_PAT"
```

---

### Step 2: Link a Figma file

Ask the user:

> "Paste your Figma URL. This can be:
> - A **file URL** (e.g. `figma.com/design/ABC123/My-File`) — links directly
> - A **team URL** (e.g. `figma.com/files/team/123456/Team-Name`) — lets you browse and pick"

**Parse the URL:**

```bash
node "$SETUP_SCRIPT" parse-url "<pasted_url>"
```

**If `type: "file"`:**
- Set `$CHOSEN_FILE_KEY` from the `fileKey` field.
- Call `get-file-name` to resolve the display name:
  ```bash
  node "$SETUP_SCRIPT" get-file-name "$CHOSEN_FILE_KEY" "$FIGMA_PAT"
  ```
- If ok: set `$CHOSEN_FILE_NAME`, print `Found file: {name}`. Skip to **Step 3**.
- If error: show error, re-ask.

**If `type: "team"`:**
- Set `$FIGMA_TEAM_ID` from `teamId`.
- Save to `$FIGMA_ENV_FILE` (same pattern as saving PAT above, using `FIGMA_TEAM_ID=` key).
- Enumerate files:
  ```bash
  node "$SETUP_SCRIPT" list-files "$FIGMA_TEAM_ID" "$FIGMA_PAT"
  ```
- Format a numbered list grouped by project:
  ```
    [Project Name]
      1. File Name  (last modified: 2026-01-15)
      2. Another File  (last modified: 2026-01-10)
  ```
- Ask: "Which file should I link to this project? Enter a number (or Q to quit):"
- Set `$CHOSEN_FILE_KEY` and `$CHOSEN_FILE_NAME` from the selection.

**If `ok: false`:** Show error, re-ask.

---

### Step 3: Write file key to CLAUDE.md

Check if `$PROJECT_ROOT/CLAUDE.md` exists. Read it if so.

**If a `## Figma` section already exists:**
Extract the current file key from the line `` File key: `...` ``.
Ask: "This project already has a Figma file linked (`{current key}`). Replace with **{CHOSEN_FILE_NAME}** (`{CHOSEN_FILE_KEY}`)? (y/N)"
If N: stop.

**Write or update the section:**

If CLAUDE.md does not exist, create it with:
```markdown
## Figma
File key: `{CHOSEN_FILE_KEY}`
```

If CLAUDE.md exists but has no `## Figma` section, append:
```markdown

## Figma
File key: `{CHOSEN_FILE_KEY}`
```

If CLAUDE.md exists and has a `## Figma` section, replace the `File key:` line with the new key.

---

### Step 4: Done

Print:

```
Figma is configured for this project.

    File:        {CHOSEN_FILE_NAME}
    Key:         {CHOSEN_FILE_KEY}
    Credentials: {FIGMA_ENV_FILE}
    Query tool:  {QUERY_SCRIPT}

From now on, when working on UI tasks, I will automatically query
Figma to get accurate design specs before writing code.
```

---

## CHANGE FILE

Use when the user wants to link a different Figma file without touching credentials.

1. Resolve paths (Step 0).
2. Read `$FIGMA_PAT` from `$FIGMA_ENV_FILE`. If missing, redirect to **SETUP**.
3. Ask: "Paste a Figma URL (file or team), or press Enter to browse your team's files:"
   - If they paste a URL: parse with `parse-url`, follow the file/team branch from Step 2.
   - If they press Enter: read `$FIGMA_TEAM_ID` from `$FIGMA_ENV_FILE`. If missing, ask for a team URL. Then run `list-files` and present the picker.
4. Run **Step 3** (write file key to CLAUDE.md).
5. Print confirmation.

---

## RECONFIGURE

Use when the user wants to re-enter credentials (new token, different team).

1. Resolve paths (Step 0).
2. Ask: "What do you want to reconfigure? (1) API token only, (2) Team ID only, (3) Both"
3. Based on choice: run Step 1 and/or the team-ID portion of Step 2, forcing the prompts even if values exist.
4. Print confirmation. No restart needed — the query helper reads credentials fresh on every call.

---

## REMOVE FILE

Remove the Figma file association from the current project's CLAUDE.md.

1. Resolve `$PROJECT_ROOT`.
2. Read `$PROJECT_ROOT/CLAUDE.md`. If no `## Figma` section exists, print "No Figma file is linked to this project." and stop.
3. Extract and show the current file key.
4. Ask: "Remove the Figma file association from this project? Global credentials are kept. (y/N)"
5. If y: remove the entire `## Figma` section from CLAUDE.md. Print confirmation.

---

## How to use Figma during frontend work

Once set up, use this workflow whenever implementing a UI component or page.
Do this **proactively** — if the project has a Figma file key in CLAUDE.md and you
are implementing UI, always check the design first without being asked.

### Query helper

All Figma data is fetched via the query helper:

```bash
node "$QUERY_SCRIPT" <command> [args...]
```

Where `$QUERY_SCRIPT` is the path resolved in Step 0:
- **Cursor**: `~/.cursor/skills/figma/query/index.mjs`
- **Claude Code**: `~/.claude/commands/figma/query/index.mjs`

The helper automatically reads credentials from `~/.figma/.env` and the file key
from the nearest CLAUDE.md. All output is JSON on stdout.

### Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `pages` | `pages [--fresh]` | List all pages and their top-level frames. Cached for 30min. |
| `children` | `children <nodeId> [--depth N]` | List children of a node. Default depth 1. |
| `node` | `node <nodeId> [--depth N] [--geometry]` | Full simplified design specs for a node subtree. |
| `download-image` | `download-image <nodeId> <path> [--scale N] [--format png\|svg]` | Export and download a node as an image. Default: 2x PNG. |

### Node IDs

Node IDs contain colons (e.g. `9134:18785`). Pass them as-is — the helper encodes them internally.

### Simplified output

The query helper strips raw Figma API bloat and returns CSS-ready properties:
- **Layout**: flex mode, gap, padding, justify, align, sizing mode (FIXED/FILL/HUG)
- **Text**: content, font, weight, size, line-height, letter-spacing, color, alignment (horizontal + vertical), font-style (italic), text-decoration (underline/strikethrough), text-transform (uppercase/lowercase/capitalize), font-variant (small-caps), paragraph-spacing, paragraph-indent, auto-resize mode, max-lines, and mixed-style segments for text with per-character formatting
- **Fills**: solid colors as hex/rgba, gradients with stops, image refs
- **Strokes**: color, weight, alignment (inside/outside/center)
- **Effects**: box-shadow and blur as ready-to-use CSS strings
- **Border radius**: single value or per-corner
- **Components**: componentId, component properties (variant, boolean, text)

### Recommended workflow

1. **Browse**: `pages` to see all pages and top-level frames.
2. **Find**: Match frame name to your UI task (e.g. "Consumer Billing Page").
3. **Explore**: `children <frameId>` to see sections/groups inside the frame.
4. **Inspect**: `node <nodeId>` on the specific component you need.
5. **Cross-reference with codebase** (see below).
6. **Implement**: Write code that respects both Figma's visual spec and the codebase's architecture.
7. **Assets**: `download-image <nodeId> <path>` for images and icons.

### Cross-referencing Figma with the codebase

**Figma is the source of truth for visuals** (colors, typography, spacing, layout, component appearance).
**The codebase is the source of truth for architecture** (component structure, naming conventions, state management, data fetching, file organization).
Neither overrides the other in its domain.

Perform this analysis after inspecting the Figma design and before writing any code:

#### Step A: Examine the project's existing architecture

Read the project's codebase to understand:
- **Component organization**: How are components structured? (atomic design, compound components, barrel exports, flat directories)
- **Styling approach**: What styling system is in use? (Tailwind, CSS Modules, styled-components, design-system library)
- **State management**: What patterns govern state? (React context, Zustand, Redux, server state via SWR/React Query)
- **Data fetching**: How does the project fetch data? (React Server Components, client-side fetching, API routes)
- **File conventions**: Naming conventions, co-location patterns, test file placement

#### Step B: Map Figma components to codebase components

For each component visible in the Figma design:
- Search the codebase for an existing component that serves the same purpose.
- If a match exists (e.g., Figma shows a "Primary Button" and the codebase has `<Button variant="primary">`): **use the existing component**, adjusting only its visual props to match Figma.
- If a partial match exists (e.g., Figma has a `ButtonGroup` but the codebase only has standalone buttons): **extend the existing pattern** rather than creating a parallel system.
- If no match exists: create a new component following the project's established conventions for naming, file placement, and export style.

#### Step C: Perform a component gap analysis

After examining both Figma and the codebase, assess alignment:
- **Figma has stronger componentization** (e.g., Figma defines a reusable `StatusBadge` component but the codebase hard-codes status badges inline): Flag this to the developer as a recommendation to tighten the codebase's component architecture.
- **Codebase has stronger componentization** (e.g., the codebase has a reusable `<DataCard>` but Figma shows inconsistent card designs): Flag this to the developer as a recommendation to advise the design team to align their Figma components.
- Report these findings before starting implementation so the developer can decide how to proceed.

#### Step D: Implement within existing constraints

- **Never introduce new architectural patterns** to match Figma. If the codebase uses Tailwind, implement in Tailwind. If CSS Modules, use CSS Modules.
- **Never restructure the file system** to match Figma's page/frame hierarchy. Map Figma pages to the codebase's existing route/page structure.
- **Preserve existing component APIs**. If an existing `<Card>` has a specific prop interface, extend it if needed rather than creating a `<FigmaCard>` duplicate.

### Rate limiting

The helper retries automatically on 429 with exponential backoff (up to 3 retries).
If Figma returns a Retry-After longer than 60 seconds, it fails fast with an actionable error message — this typically means the file is in a Starter-plan workspace.

### Example

```bash
# Resolve the query script path for your platform first (see Step 0)
Q="$QUERY_SCRIPT"

# 1. See file structure
node "$Q" pages

# 2. Explore the Components page
node "$Q" children "7792:9155"

# 3. Get button specs
node "$Q" node "7785:6575"

# 4. Download an icon
node "$Q" download-image "345:678" "./public/icons/check.svg" --format svg --scale 1
```
