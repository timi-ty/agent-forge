#!/usr/bin/env node
/**
 * ClickUp runtime query helper — direct API access with rate limiting,
 * caching, and response simplification.
 *
 * Commands:
 *   tasks [--status X] [--assignee X] [--fresh]
 *   task <task_id>
 *   comments <task_id>
 *   search <query>
 *   download-attachment <url> <path>
 *   statuses
 *
 * Credentials: reads CLICKUP_API_TOKEN from ~/.clickup/.env
 * Project context: reads Team ID and View ID from nearest CLAUDE.md
 * All output is JSON on stdout. Diagnostics go to stderr.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import { join, dirname, resolve } from "node:path";
import { tmpdir, homedir } from "node:os";

// ─── Utilities ───────────────────────────────────────────────────────────────

function fatal(message, status) {
  console.log(JSON.stringify({ ok: false, error: message, status: status ?? null }));
  process.exit(1);
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function formatDate(ms) {
  if (!ms) return undefined;
  return new Date(parseInt(ms, 10)).toISOString().slice(0, 10);
}

function formatTimestamp(ms) {
  if (!ms) return undefined;
  return new Date(parseInt(ms, 10)).toISOString();
}

// ─── Configuration ───────────────────────────────────────────────────────────

function resolveConfig() {
  // 1. API token from ~/.clickup/.env
  const envPath = join(homedir(), ".clickup", ".env");
  let apiToken = null;
  try {
    const env = readFileSync(envPath, "utf8");
    const m = env.match(/^CLICKUP_API_TOKEN=(.+)$/m);
    if (m) apiToken = m[1].trim();
  } catch {}
  if (!apiToken) {
    fatal('No CLICKUP_API_TOKEN found in ~/.clickup/.env. Run "set up clickup" first.');
  }

  // 2. Team ID and View ID from nearest CLAUDE.md walking up from cwd
  let dir = process.cwd();
  let teamId = null;
  let viewId = null;
  while (true) {
    const claudeMd = join(dir, "CLAUDE.md");
    if (existsSync(claudeMd)) {
      const content = readFileSync(claudeMd, "utf8");
      const clickupSection = content.split(/^## ClickUp\b/m)[1];
      if (clickupSection) {
        const teamMatch = clickupSection.match(/^Team ID:\s*`([^`]+)`/m);
        const viewMatch = clickupSection.match(/^View ID:\s*`([^`]+)`/m);
        if (teamMatch) teamId = teamMatch[1];
        if (viewMatch) viewId = viewMatch[1];
        if (teamId && viewId) break;
      }
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  if (!teamId || !viewId) {
    fatal('No ClickUp Team ID / View ID found in any CLAUDE.md above cwd. Run "set up clickup" to link a view.');
  }

  return { apiToken, teamId, viewId };
}

// ─── HTTP layer with rate limit retry ────────────────────────────────────────

const CLICKUP_API = "https://api.clickup.com/api/v2";
const MAX_RETRIES = 3;

async function clickupGet(path, apiToken) {
  let lastError;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const res = await fetch(`${CLICKUP_API}${path}`, {
      headers: { Authorization: apiToken },
    });

    if (res.ok) return res.json();

    if (res.status === 429) {
      const retryAfter = res.headers.get("retry-after") || res.headers.get("x-ratelimit-reset");
      let waitSec;
      if (retryAfter) {
        const parsed = parseInt(retryAfter, 10);
        waitSec = parsed > 1e9 ? Math.max(Math.ceil(parsed - Date.now() / 1000), 1) : parsed;
      } else {
        waitSec = Math.pow(2, attempt);
      }

      if (waitSec > 60) {
        fatal(
          `Rate limit exceeded. ClickUp requires a ${waitSec} second wait. ` +
            "This token is temporarily rate-limited. Options: (1) wait for the limit to reset, " +
            "(2) reduce API call frequency.",
          429
        );
      }

      if (attempt < MAX_RETRIES) {
        const waitMs = Math.max(waitSec * 1000, 1000);
        process.stderr.write(
          `Rate limited (429). Retry ${attempt + 1}/${MAX_RETRIES} in ${waitMs}ms...\n`
        );
        await sleep(waitMs);
        continue;
      }
    }

    const text = await res.text().catch(() => "");
    lastError = { status: res.status, text };
    break;
  }

  const { status, text } = lastError;
  const msg =
    status === 401 || status === 403
      ? "Authentication failed. Check your ClickUp API token."
      : status === 404
        ? "Resource not found. Check the task ID or view ID."
        : `ClickUp API ${status}: ${text}`;
  fatal(msg, status);
}

// ─── Task simplification ────────────────────────────────────────────────────

function simplifyTaskBrief(task) {
  const out = {
    id: task.id,
    name: task.name,
    status: task.status?.status,
    url: task.url,
  };
  if (task.custom_id) out.customId = task.custom_id;
  if (task.priority?.priority) out.priority = task.priority.priority;
  if (task.assignees?.length) {
    out.assignees = task.assignees.map((a) => a.username || a.email).filter(Boolean);
  }
  if (task.due_date) out.dueDate = formatDate(task.due_date);
  if (task.tags?.length) out.tags = task.tags.map((t) => t.name);
  return out;
}

function simplifyTaskFull(task) {
  const out = {
    id: task.id,
    name: task.name,
    status: task.status?.status,
    url: task.url,
  };

  if (task.custom_id) out.customId = task.custom_id;
  if (task.text_content) out.description = task.text_content;
  if (task.priority?.priority) out.priority = task.priority.priority;

  if (task.assignees?.length) {
    out.assignees = task.assignees.map((a) => ({
      id: a.id,
      username: a.username,
      email: a.email,
    }));
  }

  if (task.due_date) out.dueDate = formatDate(task.due_date);
  if (task.start_date) out.startDate = formatDate(task.start_date);
  if (task.date_created) out.dateCreated = formatTimestamp(task.date_created);
  if (task.date_updated) out.dateUpdated = formatTimestamp(task.date_updated);
  if (task.date_closed) out.dateClosed = formatTimestamp(task.date_closed);

  if (task.creator) {
    out.creator = task.creator.username || task.creator.email;
  }

  if (task.tags?.length) out.tags = task.tags.map((t) => t.name);

  if (task.custom_fields?.length) {
    const populated = task.custom_fields.filter((f) => f.value != null && f.value !== "");
    if (populated.length) {
      out.customFields = populated.map((f) => {
        const field = { name: f.name, type: f.type };
        // Resolve dropdown/label values from type_config options
        if (f.type_config?.options && typeof f.value === "number") {
          const opt = f.type_config.options[f.value];
          field.value = opt?.name ?? opt?.label ?? f.value;
        } else {
          field.value = f.value;
        }
        return field;
      });
    }
  }

  if (task.attachments?.length) {
    out.attachments = task.attachments.map((a) => ({
      id: a.id,
      title: a.title || a.name,
      url: a.url,
      type: a.extension,
    }));
  }

  if (task.subtasks?.length) {
    out.subtasks = task.subtasks.map(simplifyTaskBrief);
  }

  if (task.checklists?.length) {
    out.checklists = task.checklists.map((cl) => ({
      name: cl.name,
      items: (cl.items ?? []).map((item) => ({
        name: item.name,
        resolved: item.resolved,
        assignee: item.assignee?.username || item.assignee?.email || undefined,
      })),
    }));
  }

  if (task.dependencies?.length) {
    out.dependencies = task.dependencies.map((d) => ({
      taskId: d.depends_on ?? d.task_id,
      type: d.type,
    }));
  }

  if (task.list) out.list = { id: task.list.id, name: task.list.name };
  if (task.folder?.name) out.folder = task.folder.name;
  if (task.space?.id) out.spaceId = task.space.id;

  return out;
}

// ─── Cache ───────────────────────────────────────────────────────────────────

const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

function cachePath(viewId) {
  return join(tmpdir(), `clickup-cache-${viewId}.json`);
}

function readCache(viewId) {
  try {
    const raw = JSON.parse(readFileSync(cachePath(viewId), "utf8"));
    if (Date.now() - raw.timestamp < CACHE_TTL_MS) return raw.data;
  } catch {}
  return null;
}

function writeCache(viewId, data) {
  writeFileSync(cachePath(viewId), JSON.stringify({ timestamp: Date.now(), data }));
}

// ─── Commands ────────────────────────────────────────────────────────────────

async function cmdTasks(flags) {
  const { apiToken, viewId } = resolveConfig();

  if (!flags.fresh) {
    const cached = readCache(viewId);
    if (cached) {
      const filtered = applyTaskFilters(cached, flags);
      console.log(JSON.stringify({ ok: true, cached: true, total: cached.length, tasks: filtered }));
      return;
    }
  }

  // Paginate through all tasks in the view (up to 5 pages / ~500 tasks)
  const allTasks = [];
  const MAX_PAGES = 5;
  for (let page = 0; page < MAX_PAGES; page++) {
    const data = await clickupGet(`/view/${viewId}/task?page=${page}`, apiToken);
    const tasks = (data.tasks ?? []).map(simplifyTaskBrief);
    allTasks.push(...tasks);
    if (data.last_page) break;
  }

  writeCache(viewId, allTasks);
  const filtered = applyTaskFilters(allTasks, flags);
  console.log(JSON.stringify({ ok: true, cached: false, total: allTasks.length, tasks: filtered }));
}

function applyTaskFilters(tasks, flags) {
  let result = tasks;
  if (flags.status) {
    const s = flags.status.toLowerCase();
    result = result.filter((t) => t.status?.toLowerCase() === s);
  }
  if (flags.assignee) {
    const a = flags.assignee.toLowerCase();
    result = result.filter(
      (t) => t.assignees?.some((name) => name.toLowerCase().includes(a))
    );
  }
  return result;
}

async function cmdTask(taskId) {
  const { apiToken } = resolveConfig();
  const data = await clickupGet(`/task/${taskId}?include_subtasks=true`, apiToken);
  const simplified = simplifyTaskFull(data);
  console.log(JSON.stringify({ ok: true, task: simplified }));
}

async function cmdComments(taskId) {
  const { apiToken } = resolveConfig();
  const data = await clickupGet(`/task/${taskId}/comment`, apiToken);
  const comments = (data.comments ?? []).map((c) => ({
    id: c.id,
    text: c.comment_text,
    author: c.user?.username || c.user?.email,
    date: formatTimestamp(c.date),
  }));
  console.log(JSON.stringify({ ok: true, taskId, comments }));
}

async function cmdSearch(query) {
  const { apiToken, teamId } = resolveConfig();
  const needle = query.toLowerCase();

  // ClickUp API v2 has no free-text search parameter.
  // Fetch team tasks (100/page) and filter by name client-side.
  const allMatches = [];
  const MAX_PAGES = 3;
  for (let page = 0; page < MAX_PAGES; page++) {
    const data = await clickupGet(
      `/team/${teamId}/task?page=${page}&include_closed=true`,
      apiToken
    );
    const tasks = data.tasks ?? [];
    if (tasks.length === 0) break;
    for (const t of tasks) {
      if (t.name?.toLowerCase().includes(needle)) {
        allMatches.push(simplifyTaskBrief(t));
      }
    }
  }

  console.log(JSON.stringify({ ok: true, query, tasks: allMatches }));
}

async function cmdDownloadAttachment(url, outputPath) {
  const { apiToken } = resolveConfig();

  const res = await fetch(url, {
    headers: { Authorization: apiToken },
  });

  if (!res.ok) {
    fatal(`Failed to download attachment: HTTP ${res.status}`);
  }

  const absPath = resolve(outputPath);
  mkdirSync(dirname(absPath), { recursive: true });
  const buffer = Buffer.from(await res.arrayBuffer());
  await writeFile(absPath, buffer);

  console.log(
    JSON.stringify({
      ok: true,
      path: absPath,
      bytes: buffer.length,
    })
  );
}

async function cmdStatuses() {
  const { apiToken, viewId } = resolveConfig();

  // Resolve the list ID from the first task in the view
  const viewData = await clickupGet(`/view/${viewId}/task?page=0`, apiToken);
  const firstTask = (viewData.tasks ?? [])[0];
  if (!firstTask?.list?.id) {
    fatal("No tasks found in this view — cannot resolve the parent list for statuses.");
  }

  const listId = firstTask.list.id;
  const listData = await clickupGet(`/list/${listId}`, apiToken);
  const statuses = (listData.statuses ?? []).map((s) => ({
    status: s.status,
    color: s.color,
    type: s.type,
    orderindex: s.orderindex,
  }));

  console.log(JSON.stringify({
    ok: true,
    listId,
    listName: listData.name,
    statuses,
  }));
}

// ─── CLI dispatch ────────────────────────────────────────────────────────────

function parseFlags(args) {
  const flags = {};
  const positional = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--fresh") {
      flags.fresh = true;
    } else if (args[i] === "--status" && args[i + 1]) {
      flags.status = args[i + 1];
      i++;
    } else if (args[i] === "--assignee" && args[i + 1]) {
      flags.assignee = args[i + 1];
      i++;
    } else {
      positional.push(args[i]);
    }
  }
  return { flags, positional };
}

const [, , command, ...rawArgs] = process.argv;
const { flags, positional } = parseFlags(rawArgs);

switch (command) {
  case "tasks":
    await cmdTasks(flags);
    break;
  case "task":
    if (!positional[0]) fatal("Usage: node index.mjs task <task_id>");
    await cmdTask(positional[0]);
    break;
  case "comments":
    if (!positional[0]) fatal("Usage: node index.mjs comments <task_id>");
    await cmdComments(positional[0]);
    break;
  case "search":
    if (!positional[0]) fatal("Usage: node index.mjs search <query>");
    await cmdSearch(positional.join(" "));
    break;
  case "download-attachment":
    if (!positional[0] || !positional[1])
      fatal("Usage: node index.mjs download-attachment <url> <path>");
    await cmdDownloadAttachment(positional[0], positional[1]);
    break;
  case "statuses":
    await cmdStatuses();
    break;
  default:
    console.error(`Unknown command: ${command ?? "(none)"}`);
    console.error("Commands: tasks, task, comments, search, download-attachment, statuses");
    process.exit(1);
}
