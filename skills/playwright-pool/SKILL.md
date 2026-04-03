---
name: playwright-pool
description: Set up and use the Playwright browser pool MCP server. Enables multiple agents to run isolated browser sessions simultaneously without contention. Works with both Cursor and Claude Code. TRIGGER on "set up playwright pool", "install playwright pool", "browser pool", or any browser automation task where session isolation is needed. Also triggered automatically by sync-skills after first install.
---

# Playwright Pool

Manages a pool of isolated `@playwright/mcp` browser processes so multiple agents can each hold their own browser session simultaneously. Each agent acquires a `session_id`, passes it to every `browser_*` call, and releases it when done.

---

## SETUP WIZARD

Run this section when:
- sync-skills just installed this skill and directed you here
- The user says "set up playwright pool", "install playwright pool", or similar
- The user wants to reconfigure the pool

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

**@playwright/mcp — the MCP server package:**

The pool server fetches this at runtime via `npx @playwright/mcp@latest`. Pre-cache it now so the first server startup doesn't trigger a silent download:

```bash
npx @playwright/mcp@latest --version
```

This downloads and caches `@playwright/mcp` and its dependencies. If it fails (network error, proxy issue), stop and tell the user:
> "Could not reach the npm registry. Ensure you have internet access (or `HTTPS_PROXY` set if behind a proxy) and re-run setup."

---

### Step 2: Detect host tool

Determine whether you are running in **Cursor** or **Claude Code**:

- **Cursor**: Your system prompt identifies you as a Cursor agent, or you have access to the `AskQuestion` tool.
- **Claude Code**: Your system prompt identifies you as Claude Code, or you have access to the `AskUserQuestion` tool.

Set `$TOOL` to `cursor` or `claude-code` for use in all remaining steps.

---

### Step 3: Check if already installed

**Claude Code:**
```bash
claude mcp list 2>&1 | grep playwright-pool
```
If output shows `playwright-pool ... ✓ Connected`, it is already registered.

**Cursor:**
```bash
cat ~/.cursor/mcp.json 2>/dev/null | python -c "import json,sys; d=json.load(sys.stdin); print('found' if 'playwright-pool' in d.get('mcpServers',{}) else 'not found')"
```
If output is `found`, it is already registered.

If already registered:
- Ask: "playwright-pool is already registered. Do you want to (1) reconfigure it, or (2) skip to usage docs?"
- If reconfigure → continue from Step 4
- If skip → jump to the USAGE section below

---

### Step 4: Ask configuration preferences

Ask the user these questions one at a time. Accept Enter for defaults:

1. **Browser** — chromium, firefox, or webkit? *(default: chromium)*
2. **Acquire timeout** — Seconds to wait when at capacity before erroring? *(default: 30)*
3. **Max concurrent** — Hard cap on simultaneous browser processes? *(default: unlimited — the pool grows with demand and shrinks back to 1 idle when sessions are released)*

---

### Step 5: Install browser binaries

Now that the browser choice is known, tell the user:

> "Playwright needs to download the **[chosen browser]** binary (~150 MB). This is a one-time download stored in Playwright's local cache. Proceed?"

Wait for confirmation before continuing. If the user declines:
> "You can run `npx playwright install [browser]` manually whenever you're ready, then re-run this setup."
> Then stop.

Once confirmed:
```bash
npx playwright install <chosen-browser>
```

Safe to re-run — skips the download if the binary is already installed.

If the install fails:
- On Linux: system dependencies may be missing — run `npx playwright install-deps <browser>` first, then retry
- Behind a corporate proxy: set the `HTTPS_PROXY` environment variable

---

### Step 6: Locate the server source files

The server source files were installed alongside this SKILL.md by sync-skills. Find them based on `$TOOL`:

**Claude Code — macOS/Linux:**
```bash
ls ~/.claude/commands/playwright-pool/server/index.js 2>/dev/null && echo "found at global"
ls .claude/commands/playwright-pool/server/index.js 2>/dev/null && echo "found at workspace"
```

**Claude Code — Windows (Git Bash):**
```bash
ls "$USERPROFILE/.claude/commands/playwright-pool/server/index.js" 2>/dev/null && echo "found at global"
ls .claude/commands/playwright-pool/server/index.js 2>/dev/null && echo "found at workspace"
```

**Cursor — macOS/Linux:**
```bash
ls ~/.cursor/skills/playwright-pool/server/index.js 2>/dev/null && echo "found at global"
ls .cursor/skills/playwright-pool/server/index.js 2>/dev/null && echo "found at workspace"
```

**Cursor — Windows (Git Bash):**
```bash
ls "$USERPROFILE/.cursor/skills/playwright-pool/server/index.js" 2>/dev/null && echo "found at global"
ls .cursor/skills/playwright-pool/server/index.js 2>/dev/null && echo "found at workspace"
```

Use whichever location has the files. If neither is found: "Server source files are missing. Please re-run sync-skills to reinstall playwright-pool."

Set `$SKILL_SERVER_DIR` to the directory containing `index.js`.

---

### Step 7: Deploy the server files

**Claude Code — macOS/Linux:**
```bash
mkdir -p ~/.claude/mcp-servers/playwright-pool
cp "$SKILL_SERVER_DIR/index.js"     ~/.claude/mcp-servers/playwright-pool/index.js
cp "$SKILL_SERVER_DIR/package.json" ~/.claude/mcp-servers/playwright-pool/package.json
```

**Claude Code — Windows (Git Bash):**
```bash
mkdir -p "$USERPROFILE/.claude/mcp-servers/playwright-pool"
cp "$SKILL_SERVER_DIR/index.js"     "$USERPROFILE/.claude/mcp-servers/playwright-pool/index.js"
cp "$SKILL_SERVER_DIR/package.json" "$USERPROFILE/.claude/mcp-servers/playwright-pool/package.json"
```

**Cursor — macOS/Linux:**
```bash
mkdir -p ~/.cursor/mcp-servers/playwright-pool
cp "$SKILL_SERVER_DIR/index.js"     ~/.cursor/mcp-servers/playwright-pool/index.js
cp "$SKILL_SERVER_DIR/package.json" ~/.cursor/mcp-servers/playwright-pool/package.json
```

**Cursor — Windows (Git Bash):**
```bash
mkdir -p "$USERPROFILE/.cursor/mcp-servers/playwright-pool"
cp "$SKILL_SERVER_DIR/index.js"     "$USERPROFILE/.cursor/mcp-servers/playwright-pool/index.js"
cp "$SKILL_SERVER_DIR/package.json" "$USERPROFILE/.cursor/mcp-servers/playwright-pool/package.json"
```

Then write `config.json` with the user's preferences from Step 4:

```json
{
  "playwrightArgs": ["--isolated", "--browser=<browser>"],
  "acquireTimeoutMs": <timeout seconds * 1000>
}
```

If the user specified a `maxConcurrent` value, add it:
```json
{
  "maxConcurrent": <max concurrent>,
  "playwrightArgs": ["--isolated", "--browser=<browser>"],
  "acquireTimeoutMs": <timeout seconds * 1000>
}
```

**Claude Code:** write to `~/.claude/mcp-servers/playwright-pool/config.json`
**Cursor:** write to `~/.cursor/mcp-servers/playwright-pool/config.json`

---

### Step 8: Register the MCP server

**Claude Code — macOS/Linux:**
```bash
claude mcp add playwright-pool --scope user -- node "$HOME/.claude/mcp-servers/playwright-pool/index.js"
```

**Claude Code — Windows (Git Bash):**
```bash
claude mcp add playwright-pool --scope user -- node "$USERPROFILE/.claude/mcp-servers/playwright-pool/index.js"
```

**Cursor (all platforms)** — use Python to safely merge into `~/.cursor/mcp.json`, creating the file if it doesn't exist:

```bash
python -c "
import json, pathlib
home = pathlib.Path.home()
p = home / '.cursor' / 'mcp.json'
cfg = json.loads(p.read_text()) if p.exists() else {}
cfg.setdefault('mcpServers', {})['playwright-pool'] = {
    'command': 'node',
    'args': [str(home / '.cursor' / 'mcp-servers' / 'playwright-pool' / 'index.js')]
}
p.write_text(json.dumps(cfg, indent=2))
print('Registered playwright-pool in ~/.cursor/mcp.json')
"
```

Verify registration:

**Claude Code:**
```bash
claude mcp list 2>&1 | grep playwright-pool
```

**Cursor:** re-run the check from Step 3 and confirm output is `found`.

---

### Step 9: Confirm and instruct

Report what was configured:
- Tool: Claude Code or Cursor
- Pool size, browser, and timeout chosen
- Server deployed to: `~/.claude/mcp-servers/playwright-pool/` or `~/.cursor/mcp-servers/playwright-pool/`
- Config at: `[server dir]/config.json`

Then tell the user:

**Claude Code:**
> **Reload your Claude Code window to activate playwright-pool.**
> After reloading, `browser_pool_acquire`, `browser_navigate`, and all other browser tools will appear in your agent's tool list.
> To change settings later: edit the `config.json` above and reload the window.

**Cursor:**
> **Fully restart Cursor** (not just reload window) to activate playwright-pool.
> After restarting, browser pool tools will appear. You can verify in Cursor Settings > Tools and MCP.
> To change pool size later: edit the `config.json` above and restart Cursor.

---

## USAGE

Use this section when an agent needs browser automation in a multi-agent or parallel context.

### Why sessions are required

All agents share one MCP connection. Without the pool, every agent's browser calls go to the same browser instance — causing state contamination and blocking. The pool proxy manages **N isolated `@playwright/mcp` processes** and routes each agent's calls to its own dedicated browser.

### Mandatory workflow

Every agent that needs a browser **must** follow this three-step pattern:

**1. Acquire a session**
```
browser_pool_acquire({ label: "agent-name-or-task" })
→ { session_id: "s2-1719000000000", pool_status: { total: 2, available: 1, busy: 1, spawning: 0, queued: 0 } }
```

A warm browser is always kept on standby, so this returns instantly. If the standby is still spawning (rare: burst of concurrent acquires), the call waits for it. If `maxConcurrent` is set and reached, this call **blocks and queues** (up to `acquireTimeoutMs`). Do not poll — just await the result.

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
| `browser_pool_status()` | Check available/busy/spawning/queued counts. |

### Pool sizing

The pool is self-sizing: it keeps exactly **1 idle browser** (the warm standby) and grows as needed. At any moment, total processes = active sessions + 1. You never configure a pool size.

To add an optional hard cap (e.g. prevent runaway parallelism), set `maxConcurrent` in `config.json`:

```json
{
  "maxConcurrent": 8,
  "playwrightArgs": ["--isolated", "--browser=chromium"],
  "acquireTimeoutMs": 30000
}
```

Without `maxConcurrent`, the pool is unbounded.

### Error reference

| Error | Cause | Fix |
|-------|-------|-----|
| `session_id is required` | Called `browser_*` without a session | Call `browser_pool_acquire` first |
| `No active session for session_id "..."` | Session released or never acquired | Re-acquire a new session |
| `All N browsers are busy and maxConcurrent (M) is reached. Timed out after Xms` | Hard cap hit | Increase `maxConcurrent` or ensure agents release promptly |
