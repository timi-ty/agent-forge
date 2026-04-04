#!/usr/bin/env node
/**
 * Figma setup helper — non-interactive API utility.
 *
 * Usage:
 *   node index.mjs validate-pat <api_key>
 *   node index.mjs list-files <team_id> <api_key>
 *   node index.mjs parse-url <url>
 *   node index.mjs get-file-name <file_key> <api_key>
 *
 * All output is JSON on stdout. Exit code 0 = success, 1 = error.
 */

const [, , command, ...args] = process.argv;

const FIGMA_API_BASE = "https://api.figma.com/v1";
const MAX_RETRIES = 3;

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function figmaGet(path, apiKey) {
  let lastError;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const res = await fetch(`${FIGMA_API_BASE}${path}`, {
      headers: { "X-Figma-Token": apiKey },
    });

    if (res.ok) return res.json();

    if (res.status === 429) {
      const retryAfter = res.headers.get("retry-after");
      const parsed = retryAfter ? parseInt(retryAfter, 10) : NaN;
      const waitSec = !isNaN(parsed) ? parsed : Math.pow(2, attempt);

      if (waitSec > 60) {
        const hours = Math.round(waitSec / 3600);
        const msg = `Rate limit exceeded. Figma requires a ${hours > 0 ? hours + " hour" : waitSec + " second"} wait. ` +
          "Ensure the file is in a Professional+ team workspace (not Drafts). " +
          "See: https://developers.figma.com/docs/rest-api/rate-limits/";
        throw Object.assign(new Error(msg), { status: 429 });
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
  throw Object.assign(new Error(`Figma API ${status}: ${text}`), { status });
}

async function validatePat(apiKey) {
  try {
    const data = await figmaGet("/me", apiKey);
    console.log(JSON.stringify({ ok: true, name: data.handle, email: data.email, id: data.id }));
  } catch (err) {
    const status = err.status ?? 0;
    const message =
      status === 403 || status === 401
        ? "Invalid or expired API token. Check your Figma Personal Access Token."
        : `API error: ${err.message}`;
    console.log(JSON.stringify({ ok: false, error: message, status }));
    process.exit(1);
  }
}

async function listFiles(teamId, apiKey) {
  try {
    // Fetch all projects for the team
    const projectsData = await figmaGet(`/teams/${teamId}/projects`, apiKey);
    const projects = projectsData.projects ?? [];

    if (projects.length === 0) {
      console.log(JSON.stringify({ ok: false, error: "No projects found for this team. Files must be in a team project (not Drafts). Ensure your token has the right team permissions." }));
      process.exit(1);
    }

    // Fetch all files for each project in parallel
    const projectFiles = await Promise.all(
      projects.map(async (project) => {
        try {
          const filesData = await figmaGet(`/projects/${project.id}/files`, apiKey);
          const files = (filesData.files ?? []).map((f) => ({
            projectName: project.name,
            projectId: String(project.id),
            fileName: f.name,
            fileKey: f.key,
            lastModified: f.last_modified ? f.last_modified.slice(0, 10) : null,
          }));
          return files;
        } catch {
          return [];
        }
      })
    );

    const allFiles = projectFiles.flat();

    if (allFiles.length === 0) {
      console.log(JSON.stringify({ ok: false, error: "No files found in any team project. Create a file in a team project and try again." }));
      process.exit(1);
    }

    console.log(JSON.stringify({ ok: true, files: allFiles }));
  } catch (err) {
    const status = err.status ?? 0;
    const message =
      status === 403 || status === 404
        ? `Team '${teamId}' not found or not accessible. Check the team ID and ensure your token has access.`
        : `API error: ${err.message}`;
    console.log(JSON.stringify({ ok: false, error: message, status }));
    process.exit(1);
  }
}

function parseUrl(url) {
  // File URL: figma.com/design/KEY/..., figma.com/file/KEY/..., figma.com/proto/KEY/..., figma.com/board/KEY/...
  const fileMatch = url.match(/figma\.com\/(?:design|file|proto|board)\/([a-zA-Z0-9]+)/);
  if (fileMatch) {
    let nodeId = null;
    try {
      const parsed = new URL(url);
      const rawNodeId = parsed.searchParams.get("node-id");
      if (rawNodeId) nodeId = rawNodeId.replace(/-/g, ":");
    } catch {}
    console.log(JSON.stringify({ ok: true, type: "file", fileKey: fileMatch[1], nodeId }));
    return;
  }
  // Team URL: figma.com/files/team/ID/...
  const teamMatch = url.match(/figma\.com\/files\/team\/(\d+)/);
  if (teamMatch) {
    console.log(JSON.stringify({ ok: true, type: "team", teamId: teamMatch[1] }));
    return;
  }
  console.log(JSON.stringify({ ok: false, error: "Could not parse Figma URL. Expected a file URL (figma.com/design/KEY/...) or team URL (figma.com/files/team/ID/...)." }));
  process.exit(1);
}

async function getFileName(fileKey, apiKey) {
  try {
    const data = await figmaGet(`/files/${fileKey}?depth=1`, apiKey);
    console.log(JSON.stringify({
      ok: true,
      name: data.name,
      lastModified: data.lastModified ? data.lastModified.slice(0, 10) : null,
    }));
  } catch (err) {
    const status = err.status ?? 0;
    const message =
      status === 404
        ? `File '${fileKey}' not found. Check the file key or URL.`
        : status === 403
          ? `No access to file '${fileKey}'. Ensure your token has File content (read) scope.`
          : `API error: ${err.message}`;
    console.log(JSON.stringify({ ok: false, error: message, status }));
    process.exit(1);
  }
}

switch (command) {
  case "validate-pat":
    await validatePat(args[0]);
    break;
  case "list-files":
    await listFiles(args[0], args[1]);
    break;
  case "parse-url":
    parseUrl(args[0]);
    break;
  case "get-file-name":
    await getFileName(args[0], args[1]);
    break;
  default:
    console.error(`Unknown command: ${command}`);
    console.error("Usage: node index.mjs <validate-pat|list-files|parse-url|get-file-name> [args...]");
    process.exit(1);
}
