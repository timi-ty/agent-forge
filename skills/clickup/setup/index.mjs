#!/usr/bin/env node
/**
 * ClickUp setup helper — non-interactive API utility.
 *
 * Usage:
 *   node index.mjs validate-token <token>
 *   node index.mjs get-views <team_id> <token>
 *   node index.mjs validate-view <view_id> <token>
 *   node index.mjs parse-url <url>
 *
 * All output is JSON on stdout. Exit code 0 = success, 1 = error.
 */

const [, , command, ...args] = process.argv;

const CLICKUP_API_BASE = "https://api.clickup.com/api/v2";
const MAX_RETRIES = 3;

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function clickupGet(path, token) {
  let lastError;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const res = await fetch(`${CLICKUP_API_BASE}${path}`, {
      headers: { Authorization: token },
    });

    if (res.ok) return res.json();

    if (res.status === 429) {
      const retryAfter = res.headers.get("retry-after") || res.headers.get("x-ratelimit-reset");
      let waitSec;
      if (retryAfter) {
        const parsed = parseInt(retryAfter, 10);
        // x-ratelimit-reset is a Unix timestamp; retry-after is seconds
        waitSec = parsed > 1e9 ? Math.max(Math.ceil(parsed - Date.now() / 1000), 1) : parsed;
      } else {
        waitSec = Math.pow(2, attempt);
      }

      if (waitSec > 60) {
        throw Object.assign(
          new Error(
            `Rate limit exceeded. ClickUp requires a ${waitSec} second wait. ` +
            "Reduce API call frequency or wait for the limit to reset."
          ),
          { status: 429 }
        );
      }

      if (attempt < MAX_RETRIES) {
        const waitMs = Math.max(waitSec * 1000, 1000);
        process.stderr.write(`Rate limited (429). Retry ${attempt + 1}/${MAX_RETRIES} in ${waitMs}ms...\n`);
        await sleep(waitMs);
        continue;
      }
    }

    const text = await res.text().catch(() => "");
    lastError = { status: res.status, text };
    break;
  }

  const { status, text } = lastError;
  throw Object.assign(new Error(`ClickUp API ${status}: ${text}`), { status });
}

// ─── Commands ───────────────────────────────────────────────────────────────

async function validateToken(token) {
  try {
    const data = await clickupGet("/user", token);
    const user = data.user ?? data;
    console.log(JSON.stringify({
      ok: true,
      name: user.username ?? user.name,
      email: user.email,
      id: user.id,
    }));
  } catch (err) {
    const status = err.status ?? 0;
    const message =
      status === 401 || status === 403
        ? "Invalid or expired API token. Check your ClickUp Personal API Token."
        : `API error: ${err.message}`;
    console.log(JSON.stringify({ ok: false, error: message, status }));
    process.exit(1);
  }
}

async function getViews(teamId, token) {
  try {
    // Step 1: Get all spaces
    const spacesData = await clickupGet(`/team/${teamId}/space?archived=false`, token);
    const spaces = spacesData.spaces ?? [];

    if (spaces.length === 0) {
      console.log(JSON.stringify({ ok: false, error: "No spaces found for this workspace. Create a space and try again." }));
      process.exit(1);
    }

    const allViews = [];

    // Step 2: For each space, get folders + folderless lists + space-level views in parallel
    await Promise.all(
      spaces.map(async (space) => {
        const [foldersRes, folderlessListsRes] = await Promise.all([
          clickupGet(`/space/${space.id}/folder?archived=false`, token).catch(() => ({ folders: [] })),
          clickupGet(`/space/${space.id}/list?archived=false`, token).catch(() => ({ lists: [] })),
        ]);

        const folders = foldersRes.folders ?? [];
        const folderlessLists = folderlessListsRes.lists ?? [];

        // Step 3: Get views for folderless lists
        const folderlessViewPromises = folderlessLists.map(async (list) => {
          const viewsRes = await clickupGet(`/list/${list.id}/view`, token).catch(() => ({ views: [] }));
          for (const v of viewsRes.views ?? []) {
            allViews.push({
              viewId: v.id,
              viewName: v.name,
              viewType: v.type,
              listName: list.name,
              listId: list.id,
              folderName: null,
              spaceName: space.name,
            });
          }
        });

        // Step 4: For each folder, get lists, then views for each list
        const folderPromises = folders.map(async (folder) => {
          const folderListsRes = await clickupGet(
            `/folder/${folder.id}/list?archived=false`, token
          ).catch(() => ({ lists: [] }));
          const lists = folderListsRes.lists ?? [];

          await Promise.all(
            lists.map(async (list) => {
              const viewsRes = await clickupGet(`/list/${list.id}/view`, token).catch(() => ({ views: [] }));
              for (const v of viewsRes.views ?? []) {
                allViews.push({
                  viewId: v.id,
                  viewName: v.name,
                  viewType: v.type,
                  listName: list.name,
                  listId: list.id,
                  folderName: folder.name,
                  spaceName: space.name,
                });
              }
            })
          );
        });

        await Promise.all([...folderlessViewPromises, ...folderPromises]);
      })
    );

    if (allViews.length === 0) {
      console.log(JSON.stringify({ ok: false, error: "No views found in any list. Create a view in ClickUp and try again." }));
      process.exit(1);
    }

    console.log(JSON.stringify({ ok: true, views: allViews }));
  } catch (err) {
    const status = err.status ?? 0;
    const message =
      status === 401 || status === 403
        ? `Workspace '${teamId}' not accessible. Check the workspace ID and ensure your token has access.`
        : status === 404
          ? `Workspace '${teamId}' not found. Check the workspace ID.`
          : `API error: ${err.message}`;
    console.log(JSON.stringify({ ok: false, error: message, status }));
    process.exit(1);
  }
}

async function validateView(viewId, token) {
  try {
    const data = await clickupGet(`/view/${viewId}/task?page=0`, token);
    const taskCount = (data.tasks ?? []).length;
    console.log(JSON.stringify({ ok: true, taskCount }));
  } catch (err) {
    const status = err.status ?? 0;
    const message =
      status === 404
        ? `View '${viewId}' not found. Check the view ID or URL.`
        : status === 401 || status === 403
          ? `No access to view '${viewId}'. Ensure your token has access to this workspace.`
          : `API error: ${err.message}`;
    console.log(JSON.stringify({ ok: false, error: message, status }));
    process.exit(1);
  }
}

function parseUrl(url) {
  // View URL: app.clickup.com/{team_id}/v/{type}/{view_id}
  // Types: l (list), b (board), li (list alt), dc (doc), g (gantt), mn (mind map), etc.
  const viewMatch = url.match(/app\.clickup\.com\/(\d+)\/v\/[a-z]+\/([\w-]+)/);
  if (viewMatch) {
    console.log(JSON.stringify({ ok: true, type: "view", teamId: viewMatch[1], viewId: viewMatch[2] }));
    return;
  }

  // Workspace URL: app.clickup.com/{team_id} (just the workspace, no deeper path)
  const workspaceMatch = url.match(/app\.clickup\.com\/(\d+)(?:\/home|\/?)(?:\?.*)?$/);
  if (workspaceMatch) {
    console.log(JSON.stringify({ ok: true, type: "workspace", teamId: workspaceMatch[1] }));
    return;
  }

  // Task URL: app.clickup.com/t/{task_id}
  const taskMatch = url.match(/app\.clickup\.com\/t\/([\w-]+)/);
  if (taskMatch) {
    console.log(JSON.stringify({ ok: true, type: "task", taskId: taskMatch[1] }));
    return;
  }

  console.log(JSON.stringify({
    ok: false,
    error: "Could not parse ClickUp URL. Expected a view URL (app.clickup.com/{team_id}/v/l/{view_id}) or workspace URL (app.clickup.com/{team_id}).",
  }));
  process.exit(1);
}

// ─── Dispatch ───────────────────────────────────────────────────────────────

switch (command) {
  case "validate-token":
    await validateToken(args[0]);
    break;
  case "get-views":
    await getViews(args[0], args[1]);
    break;
  case "validate-view":
    await validateView(args[0], args[1]);
    break;
  case "parse-url":
    parseUrl(args[0]);
    break;
  default:
    console.error(`Unknown command: ${command}`);
    console.error("Usage: node index.mjs <validate-token|get-views|validate-view|parse-url> [args...]");
    process.exit(1);
}
