---
name: playwright-pool
description: Set up and use the Playwright browser pool MCP server. Enables multiple Claude Code agents to run isolated browser sessions simultaneously without contention. TRIGGER on "set up playwright pool", "install playwright pool", "browser pool", or any browser automation task where session isolation is needed. Also triggered automatically by sync-skills after first install.
---

# Playwright Pool

Manages a pool of isolated `@playwright/mcp` browser processes so multiple agents can each hold their own browser session simultaneously. Each agent acquires a `session_id`, passes it to every `browser_*` call, and releases it when done.

---

## SETUP WIZARD

Run this section when:
- sync-skills just installed this skill and directed you here
- The user says "set up playwright pool", "install playwright pool", or similar
- The user wants to reconfigure the pool

**Claude Code only.** This skill installs a Node.js MCP server and is not compatible with Cursor.

---

### Step 1: Check prerequisites

**Node.js — required to run the MCP server:**
```bash
node --version
```

If the command fails or returns a version below 18, tell the user:
> "Node.js 18 or later is required. Install it from https://nodejs.org and re-run setup."
> Then stop.

**npx — ships with Node.js, but verify:**
```bash
npx --version
```

If this fails, tell the user to reinstall Node.js (npx is bundled with it).

**Playwright browser binaries — required for browsers to launch:**

The pool server fetches `@playwright/mcp` automatically via npx at runtime, but the actual browser executables must be installed separately. Tell the user:

> "Playwright needs to download the Chromium browser binary (~150 MB). This is a one-time download and will be stored in Playwright's local cache. Proceed?"

Wait for confirmation before continuing. If the user declines, tell them:
> "You can run `npx playwright install chromium` manually whenever you're ready, then re-run this setup."
> Then stop.

Once confirmed, run:
```bash
npx playwright install chromium
```

Safe to re-run — skips the download if Chromium is already installed.

If the install fails:
- On Linux: system dependencies may be missing — run `npx playwright install-deps chromium` first, then retry
- Behind a corporate proxy: set the `HTTPS_PROXY` environment variable

---

### Step 2: Check if already installed

```bash
claude mcp list 2>&1 | grep playwright-pool
```

If output shows `playwright-pool ... ✓ Connected`:
- Ask: "playwright-pool is already registered. Do you want to (1) reconfigure it, or (2) skip to usage docs?"
- If reconfigure → continue from Step 3
- If skip → jump to the USAGE section below

---

### Step 3: Locate the server source files

The server source files were installed alongside this SKILL.md by sync-skills. Find them:

**macOS/Linux:**
```bash
ls ~/.claude/commands/playwright-pool/server/index.js 2>/dev/null && echo "found at global"
ls .claude/commands/playwright-pool/server/index.js 2>/dev/null && echo "found at workspace"
```

**Windows (Git Bash):**
```bash
ls "$USERPROFILE/.claude/commands/playwright-pool/server/index.js" 2>/dev/null && echo "found at global"
ls .claude/commands/playwright-pool/server/index.js 2>/dev/null && echo "found at workspace"
```

Use whichever location has the files. If neither is found, tell the user: "Server source files are missing. Please re-run sync-skills to reinstall playwright-pool."

Set `$SKILL_SERVER_DIR` to the directory containing `index.js` (`~/.claude/commands/playwright-pool/server/` or equivalent).

---

### Step 4: Ask configuration preferences

Ask the user these questions one at a time. Accept Enter for defaults:

1. **Pool size** — How many parallel browser instances? *(default: 4)*
2. **Browser** — chromium, firefox, or webkit? *(default: chromium)*
3. **Acquire timeout** — Seconds to wait for a free slot before erroring? *(default: 30)*

If the user chose firefox or webkit in question 2, install those binaries now before continuing:

```bash
npx playwright install firefox    # if firefox was chosen
npx playwright install webkit     # if webkit was chosen
```

---

### Step 5: Deploy the server files

Create the MCP server directory and copy the files:

**macOS/Linux:**
```bash
mkdir -p ~/.claude/mcp-servers/playwright-pool
cp "$SKILL_SERVER_DIR/index.js"     ~/.claude/mcp-servers/playwright-pool/index.js
cp "$SKILL_SERVER_DIR/package.json" ~/.claude/mcp-servers/playwright-pool/package.json
```

**Windows (Git Bash):**
```bash
mkdir -p "$USERPROFILE/.claude/mcp-servers/playwright-pool"
cp "$SKILL_SERVER_DIR/index.js"     "$USERPROFILE/.claude/mcp-servers/playwright-pool/index.js"
cp "$SKILL_SERVER_DIR/package.json" "$USERPROFILE/.claude/mcp-servers/playwright-pool/package.json"
```

Then write `config.json` with the user's chosen preferences from Step 4:

```json
{
  "poolSize": <pool size>,
  "playwrightArgs": ["--isolated", "--browser=<browser>"],
  "acquireTimeoutMs": <timeout seconds * 1000>
}
```

Write to `~/.claude/mcp-servers/playwright-pool/config.json` (or `$USERPROFILE` equivalent on Windows).

---

### Step 6: Register the MCP server

**macOS/Linux:**
```bash
claude mcp add playwright-pool --scope user -- node "$HOME/.claude/mcp-servers/playwright-pool/index.js"
```

**Windows (Git Bash):**
```bash
claude mcp add playwright-pool --scope user -- node "$USERPROFILE/.claude/mcp-servers/playwright-pool/index.js"
```

Verify it registered:
```bash
claude mcp list 2>&1 | grep playwright-pool
```

---

### Step 7: Confirm and instruct

Report what was configured:
- Pool size, browser, and timeout chosen
- Server deployed to: `~/.claude/mcp-servers/playwright-pool/`
- Config at: `~/.claude/mcp-servers/playwright-pool/config.json`

Then tell the user:

> **Reload your Claude Code window to activate playwright-pool.**
> After reloading, `browser_pool_acquire`, `browser_navigate`, and all other browser tools will appear in your agent's tool list.
>
> To change pool size later: edit `~/.claude/mcp-servers/playwright-pool/config.json` and reload the window.

---

## USAGE

Use this section when an agent needs browser automation in a multi-agent or parallel context.

### Why sessions are required

All Claude Code agents share one MCP connection. Without the pool, every agent's browser calls go to the same browser instance — causing state contamination and blocking. The pool proxy manages **N isolated `@playwright/mcp` processes** and routes each agent's calls to its own dedicated browser.

### Mandatory workflow

Every agent that needs a browser **must** follow this three-step pattern:

**1. Acquire a session**
```
browser_pool_acquire({ label: "agent-name-or-task" })
→ { session_id: "s2-1719000000000", pool_status: { total: 4, available: 3, busy: 1, queued: 0 } }
```

If all browsers are busy, this call **blocks and queues** (up to `acquireTimeoutMs`). Do not poll — just await the result.

**2. Use the browser — pass `session_id` to every call**
```
browser_navigate({ session_id: "s2-...", url: "https://example.com" })
browser_snapshot({ session_id: "s2-..." })
browser_click({ session_id: "s2-...", ref: "button#submit" })
```

Every `browser_*` call requires `session_id`. Calls without it fail immediately.

**3. Always release when done**
```
browser_pool_release({ session_id: "s2-..." })
```

**Always release — even if an error occurred.** Unreleased sessions stay busy until the pool restarts.

### Pool management tools

| Tool | Purpose |
|------|---------|
| `browser_pool_acquire({ label? })` | Get a free browser. Queues if pool is full. |
| `browser_pool_release({ session_id })` | Return browser to pool. |
| `browser_pool_status()` | Check available/busy/queued counts. |

### Scaling the pool

Edit `~/.claude/mcp-servers/playwright-pool/config.json` and reload the window:

```json
{
  "poolSize": 4,
  "playwrightArgs": ["--isolated", "--browser=chromium"],
  "acquireTimeoutMs": 30000
}
```

Each pool slot is one OS-level browser process. `poolSize: 8` means 8 parallel Chromium instances.

### Error reference

| Error | Cause | Fix |
|-------|-------|-----|
| `session_id is required` | Called `browser_*` without a session | Call `browser_pool_acquire` first |
| `No active session for session_id "..."` | Session released or never acquired | Re-acquire a new session |
| `All N browsers are busy. Timed out after Xms` | Pool exhausted | Increase `poolSize` or ensure agents release promptly |
