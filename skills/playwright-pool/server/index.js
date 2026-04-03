/**
 * playwright-pool — Pooling MCP proxy for @playwright/mcp
 *
 * Manages N isolated @playwright/mcp child processes so multiple Claude Code
 * agents can each hold their own browser session simultaneously.
 *
 * Protocol:
 *   1. Agent calls browser_pool_acquire({ label? }) → gets a session_id
 *   2. Agent passes session_id to every browser_* tool call
 *   3. Agent calls browser_pool_release({ session_id }) when done
 *
 * Configuration: edit config.json in this directory.
 *   maxConcurrent    — optional cap on simultaneous browser processes (default: unlimited)
 *   playwrightArgs   — CLI args forwarded to @playwright/mcp (default: ["--isolated"])
 *   acquireTimeoutMs — ms to wait when at maxConcurrent before erroring (default: 30000)
 *
 * The pool keeps exactly one idle browser as a warm standby. On acquire the standby
 * is handed out and a replacement is spawned immediately. On release, if a standby
 * already exists the released browser is killed — so idle memory is always just one
 * process. Total live processes = active sessions + 1 (the standby).
 */

import { spawn }          from 'child_process';
import { createInterface } from 'readline';
import { readFileSync }    from 'fs';
import { fileURLToPath }   from 'url';
import { dirname, join }   from 'path';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const __dirname = dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(readFileSync(join(__dirname, 'config.json'), 'utf8'));

const {
  maxConcurrent    = Infinity,
  playwrightArgs   = ['--isolated'],
  acquireTimeoutMs = 30000,
} = config;

// ---------------------------------------------------------------------------
// Pool state
// ---------------------------------------------------------------------------

const pool = [];          // ChildEntry[]
const acquireQueue = [];  // { label, resolve, reject, timer }[]
let   mergedTools  = [];  // built from probe child at startup
let   nextIndex    = 0;   // ever-incrementing child index counter

// ---------------------------------------------------------------------------
// Child process management
// ---------------------------------------------------------------------------

async function spawnChild(index) {
  const proc = spawn('npx', ['@playwright/mcp@latest', ...playwrightArgs], {
    stdio:  ['pipe', 'pipe', 'pipe'],
    shell:  true,
  });

  proc.stderr.on('data', d => process.stderr.write(`[child-${index}] ${d}`));

  const child = {
    index,
    process:   proc,
    state:     'initializing', // 'available' | 'busy' | 'initializing'
    sessionId: null,
    label:     null,
    reqId:     0,
    pending:   new Map(),      // childReqId → { resolve, reject }
    tools:     [],
  };

  // Single readline for the lifetime of this child — handles both init and
  // forwarded tool-call responses.
  const rl = createInterface({ input: proc.stdout, crlfDelay: Infinity });
  rl.on('line', line => {
    line = line.trim();
    if (!line) return;
    let msg;
    try { msg = JSON.parse(line); } catch { return; }
    if (msg.id === undefined) return; // notifications have no id — ignore
    const p = child.pending.get(msg.id);
    if (!p) return;
    child.pending.delete(msg.id);
    if (msg.error) p.reject(new Error(msg.error.message || JSON.stringify(msg.error)));
    else           p.resolve(msg.result);
  });

  pool.push(child);
  await initHandshake(child);
  return child;
}

// Write a raw JSON-RPC message to a child's stdin.
function writeToChild(child, msg) {
  child.process.stdin.write(JSON.stringify(msg) + '\n');
}

// Send a request to a child and return a promise for its response.
function requestChild(child, method, params) {
  return new Promise((resolve, reject) => {
    const id = ++child.reqId;
    child.pending.set(id, { resolve, reject });
    writeToChild(child, {
      jsonrpc: '2.0',
      id,
      method,
      ...(params !== undefined ? { params } : {}),
    });
  });
}

// Perform the MCP initialize handshake and fetch the tools list.
async function initHandshake(child) {
  await requestChild(child, 'initialize', {
    protocolVersion: '2024-11-05',
    capabilities:    {},
    clientInfo:      { name: 'playwright-pool', version: '1.0.0' },
  });
  writeToChild(child, { jsonrpc: '2.0', method: 'notifications/initialized' });
  const result  = await requestChild(child, 'tools/list');
  child.tools   = result.tools || [];
  child.state   = 'available';

  // If a caller was queued waiting for a slot, hand this child directly to them.
  if (acquireQueue.length > 0) {
    const next = acquireQueue.shift();
    clearTimeout(next.timer);
    child.state     = 'busy';
    child.sessionId = `s${child.index}-${Date.now()}`;
    child.label     = next.label || null;
    next.resolve(child);
  }
}

// ---------------------------------------------------------------------------
// Tool schema patching
// ---------------------------------------------------------------------------

// Add a required `session_id` parameter to a browser_* tool's schema.
function patchTool(tool) {
  const t = JSON.parse(JSON.stringify(tool));
  t.inputSchema              = t.inputSchema              || { type: 'object', properties: {} };
  t.inputSchema.properties   = t.inputSchema.properties   || {};
  t.inputSchema.required     = [...(t.inputSchema.required || [])];

  t.inputSchema.properties.session_id = {
    type:        'string',
    description: 'Session ID returned by browser_pool_acquire. Required for all browser_* tools.',
  };
  if (!t.inputSchema.required.includes('session_id')) {
    t.inputSchema.required.push('session_id');
  }
  return t;
}

// The three pool-management tools exposed to agents.
const POOL_TOOLS = [
  {
    name: 'browser_pool_acquire',
    description:
      'Acquire an isolated browser session from the pool. ' +
      'Returns a session_id that MUST be passed to every subsequent browser_* call. ' +
      'If all browsers are busy the call will queue and wait up to acquireTimeoutMs milliseconds. ' +
      'Always call browser_pool_release when finished — even if an error occurred.',
    inputSchema: {
      type:       'object',
      properties: {
        label: {
          type:        'string',
          description: 'Optional human-readable label for this session (e.g. "scraper-agent-1"). Useful for debugging pool_status output.',
        },
      },
    },
  },
  {
    name: 'browser_pool_release',
    description:
      'Release a browser session back to the pool. ' +
      'Call this when you are done with browser automation. ' +
      'Releases the slot so other agents waiting in the queue can proceed.',
    inputSchema: {
      type:       'object',
      required:   ['session_id'],
      properties: {
        session_id: { type: 'string', description: 'The session_id returned by browser_pool_acquire.' },
      },
    },
  },
  {
    name: 'browser_pool_status',
    description: 'Check how many browser sessions are available, busy, and queued. Useful before acquiring to gauge contention.',
    inputSchema: { type: 'object', properties: {} },
  },
];

// ---------------------------------------------------------------------------
// Pool operations
// ---------------------------------------------------------------------------

function poolStatus() {
  return {
    total:     pool.length,
    available: pool.filter(c => c.state === 'available').length,
    busy:      pool.filter(c => c.state === 'busy').length,
    spawning:  pool.filter(c => c.state === 'initializing').length,
    queued:    acquireQueue.length,
  };
}

// Attempt to immediately assign a free child. Returns the child or null.
function tryAcquire(label) {
  const child = pool.find(c => c.state === 'available');
  if (!child) return null;
  child.state     = 'busy';
  child.sessionId = `s${child.index}-${Date.now()}`;
  child.label     = label || null;
  return child;
}

// Release a session. If there are waiters, hand the child directly to the
// next one without going through 'available'. Otherwise keep it as the warm
// standby — or kill it if a standby already exists.
function doRelease(sessionId) {
  const child = pool.find(c => c.sessionId === sessionId);
  if (!child) return false;

  if (acquireQueue.length > 0) {
    const next = acquireQueue.shift();
    clearTimeout(next.timer);
    child.sessionId = `s${child.index}-${Date.now()}`;
    child.label     = next.label || null;
    // state stays 'busy'
    next.resolve(child);
  } else {
    const hasStandby = pool.some(c => c.state === 'available' || c.state === 'initializing');
    if (hasStandby) {
      // Standby already covered — kill this one instead of idling it.
      try { child.process.kill(); } catch {}
      pool.splice(pool.indexOf(child), 1);
    } else {
      child.state     = 'available';
      child.sessionId = null;
      child.label     = null;
    }
  }
  return true;
}

// Spawn a warm standby if none exists, so the next acquire is instant.
function ensureWarmStandby() {
  const hasStandby = pool.some(c => c.state === 'available' || c.state === 'initializing');
  if (hasStandby) return;
  if (pool.length >= maxConcurrent) return;
  spawnChild(nextIndex++).catch(err => {
    process.stderr.write(`[playwright-pool] Standby spawn failed: ${err.message}\n`);
  });
}

// ---------------------------------------------------------------------------
// Response helpers
// ---------------------------------------------------------------------------

function writeOut(msg) {
  process.stdout.write(JSON.stringify(msg) + '\n');
}

function respond(id, result) {
  writeOut({ jsonrpc: '2.0', id, result });
}

function respondError(id, code, message) {
  writeOut({ jsonrpc: '2.0', id, error: { code, message } });
}

// Wrap a value in MCP's content envelope.
function mcpContent(value) {
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  return { content: [{ type: 'text', text }] };
}

// ---------------------------------------------------------------------------
// Tool call handlers
// ---------------------------------------------------------------------------

async function handleAcquire(id, args) {
  const label = args?.label;
  let child = tryAcquire(label);

  if (!child) {
    if (pool.length < maxConcurrent) {
      // No standby ready yet (still spawning or first call) — spawn one now and wait.
      try {
        await spawnChild(nextIndex++);
        child = tryAcquire(label);
      } catch (err) {
        respondError(id, -32000, `Failed to spawn browser: ${err.message}`);
        return;
      }
    }

    if (!child) {
      // At maxConcurrent cap — queue with timeout.
      try {
        child = await new Promise((resolve, reject) => {
          const timer = setTimeout(() => {
            const i = acquireQueue.findIndex(q => q.resolve === resolve);
            if (i !== -1) acquireQueue.splice(i, 1);
            reject(new Error(
              `All ${pool.filter(c => c.state === 'busy').length} browser(s) are busy ` +
              `and maxConcurrent (${maxConcurrent}) is reached. ` +
              `Timed out after ${acquireTimeoutMs}ms. ` +
              `Call browser_pool_status() to inspect current usage.`
            ));
          }, acquireTimeoutMs);
          acquireQueue.push({ label, resolve, reject, timer });
        });
      } catch (err) {
        respondError(id, -32000, err.message);
        return;
      }
    }
  }

  // Kick off a warm standby replacement so the next acquire is instant.
  ensureWarmStandby();

  respond(id, mcpContent({ session_id: child.sessionId, pool_status: poolStatus() }));
}

function handleRelease(id, args) {
  const { session_id } = args || {};
  if (!session_id) { respondError(id, -32602, 'session_id is required'); return; }
  const released = doRelease(session_id);
  respond(id, mcpContent({ released, pool_status: poolStatus() }));
}

function handleStatus(id) {
  respond(id, mcpContent(poolStatus()));
}

async function handleBrowserTool(id, toolName, args) {
  const { session_id, ...forwardArgs } = args || {};

  if (!session_id) {
    respondError(id, -32602,
      `session_id is required. Call browser_pool_acquire first to get one.`
    );
    return;
  }

  const child = pool.find(c => c.sessionId === session_id);
  if (!child) {
    respondError(id, -32602,
      `No active session for session_id "${session_id}". ` +
      `It may have been released or never acquired.`
    );
    return;
  }

  try {
    const result = await requestChild(child, 'tools/call', {
      name:      toolName,
      arguments: forwardArgs,
    });
    respond(id, result);
  } catch (err) {
    respondError(id, -32000, err.message);
  }
}

// ---------------------------------------------------------------------------
// Main message dispatch
// ---------------------------------------------------------------------------

async function handleMessage(msg) {
  const { id, method, params } = msg;

  switch (method) {
    case 'initialize':
      respond(id, {
        protocolVersion: params?.protocolVersion || '2024-11-05',
        capabilities:    { tools: { listChanged: false } },
        serverInfo:      { name: 'playwright-pool', version: '1.0.0' },
      });
      return;

    case 'notifications/initialized':
      return; // notification — no response

    case 'tools/list':
      respond(id, { tools: mergedTools });
      return;

    case 'tools/call': {
      const toolName = params?.name;
      const args     = params?.arguments || {};
      switch (toolName) {
        case 'browser_pool_acquire': await handleAcquire(id, args); break;
        case 'browser_pool_release':      handleRelease(id, args); break;
        case 'browser_pool_status':       handleStatus(id);        break;
        default:                    await handleBrowserTool(id, toolName, args);
      }
      return;
    }

    default:
      // ping or unrecognised — acknowledge with empty result
      if (id !== undefined) respond(id, {});
  }
}

// ---------------------------------------------------------------------------
// Startup & graceful shutdown
// ---------------------------------------------------------------------------

async function main() {
  process.stderr.write('[playwright-pool] Bootstrapping...\n');

  // Spawn a probe child solely to discover the tools list, then kill it.
  const probe = await spawnChild(nextIndex++);
  const patchedBrowserTools = probe.tools.map(t =>
    t.name.startsWith('browser_') ? patchTool(t) : t
  );
  mergedTools = [...POOL_TOOLS, ...patchedBrowserTools];
  try { probe.process.kill(); } catch {}
  pool.splice(pool.indexOf(probe), 1);

  // Spawn the initial warm standby.
  await spawnChild(nextIndex++);

  process.stderr.write(
    `[playwright-pool] Ready. 1 warm standby, ` +
    `${patchedBrowserTools.length} browser tools + ${POOL_TOOLS.length} pool tools.\n`
  );

  // Serve Claude Code over stdin/stdout.
  const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on('line', line => {
    line = line.trim();
    if (!line) return;
    let msg;
    try { msg = JSON.parse(line); } catch { return; }
    handleMessage(msg); // intentionally fire-and-forget (async)
  });
  rl.on('close', shutdown);

  function shutdown() {
    process.stderr.write('[playwright-pool] Shutting down...\n');
    for (const child of pool) {
      try { child.process.kill(); } catch {}
    }
    process.exit(0);
  }

  process.on('SIGTERM', shutdown);
  process.on('SIGINT',  shutdown);
  process.on('exit',    () => {
    for (const child of pool) {
      try { child.process.kill(); } catch {}
    }
  });
}

main().catch(err => {
  process.stderr.write(`[playwright-pool] Fatal startup error: ${err.message}\n${err.stack}\n`);
  process.exit(1);
});
