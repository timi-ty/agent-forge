#!/usr/bin/env node
/**
 * Figma runtime query helper — direct API access with rate limiting,
 * caching, node ID encoding, and response simplification.
 *
 * Commands:
 *   pages [--fresh]
 *   children <nodeId> [--depth N]
 *   node <nodeId> [--depth N] [--geometry]
 *   download-image <nodeId> <outputPath> [--scale N] [--format png|svg]
 *
 * Credentials: reads FIGMA_API_KEY from ~/.figma/.env
 * File key: reads from nearest CLAUDE.md (walks up from cwd)
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

// ─── Configuration ───────────────────────────────────────────────────────────

function resolveConfig() {
  // 1. API key from ~/.figma/.env
  const envPath = join(homedir(), ".figma", ".env");
  let apiKey = null;
  try {
    const env = readFileSync(envPath, "utf8");
    const m = env.match(/^FIGMA_API_KEY=(.+)$/m);
    if (m) apiKey = m[1].trim();
  } catch {}
  if (!apiKey) {
    fatal('No FIGMA_API_KEY found in ~/.figma/.env. Run "set up figma" first.');
  }

  // 2. File key from nearest CLAUDE.md walking up from cwd
  let dir = process.cwd();
  let fileKey = null;
  while (true) {
    const claudeMd = join(dir, "CLAUDE.md");
    if (existsSync(claudeMd)) {
      const content = readFileSync(claudeMd, "utf8");
      const figmaSection = content.split(/^## Figma\b/m)[1];
      if (figmaSection) {
        const fkMatch = figmaSection.match(/^File key:\s*`([^`]+)`/m);
        if (fkMatch) {
          fileKey = fkMatch[1];
          break;
        }
      }
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  if (!fileKey) {
    fatal('No Figma file key found in any CLAUDE.md above cwd. Run "set up figma" to link a file.');
  }

  return { apiKey, fileKey };
}

// ─── HTTP layer with rate limit retry ────────────────────────────────────────

const FIGMA_API = "https://api.figma.com/v1";
const MAX_RETRIES = 3;

async function figmaGet(path, apiKey) {
  let lastError;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const res = await fetch(`${FIGMA_API}${path}`, {
      headers: { "X-Figma-Token": apiKey },
    });

    if (res.ok) return res.json();

    if (res.status === 429) {
      const retryAfter = res.headers.get("retry-after");
      const parsed = retryAfter ? parseInt(retryAfter, 10) : NaN;
      const waitSec = !isNaN(parsed) ? parsed : Math.pow(2, attempt);

      // If Figma says wait more than 60s, the account is locked out — fail fast
      if (waitSec > 60) {
        const hours = Math.round(waitSec / 3600);
        fatal(
          `Rate limit exceeded. Figma requires a ${hours > 0 ? hours + " hour" : waitSec + " second"} wait. ` +
            "This token/account is temporarily locked out. Options: (1) wait for the lockout to expire, " +
            "(2) provision a new token from a different Figma account, or (3) reduce API call frequency.",
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
      ? "Authentication failed. Check your Figma API token."
      : status === 404
        ? "Resource not found. Check the file key and node IDs."
        : `Figma API ${status}: ${text}`;
  fatal(msg, status);
}

// ─── Node simplification ─────────────────────────────────────────────────────

function extractPadding(node) {
  const t = node.paddingTop ?? 0;
  const r = node.paddingRight ?? 0;
  const b = node.paddingBottom ?? 0;
  const l = node.paddingLeft ?? 0;
  if (t === 0 && r === 0 && b === 0 && l === 0) return undefined;
  if (t === r && r === b && b === l) return t;
  if (t === b && l === r) return `${t} ${r}`;
  return `${t} ${r} ${b} ${l}`;
}

function mapAxisAlign(val) {
  const map = {
    MIN: "flex-start",
    CENTER: "center",
    MAX: "flex-end",
    SPACE_BETWEEN: "space-between",
    BASELINE: "baseline",
  };
  return map[val] ?? val;
}

function extractLineHeight(style) {
  if (!style?.lineHeightPx) return undefined;
  if (style.lineHeightUnit === "PIXELS") return `${style.lineHeightPx}px`;
  if (style.lineHeightUnit === "FONT_SIZE_%") return `${style.lineHeightPercentFontSize}%`;
  return style.lineHeightPx;
}

function extractColor(fill) {
  if (!fill?.color) return undefined;
  const { r, g, b, a } = fill.color;
  const toHex = (v) => Math.round(v * 255).toString(16).padStart(2, "0");
  if (a != null && a < 1) {
    return `rgba(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)}, ${parseFloat(a.toFixed(2))})`;
  }
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function extractFill(fill) {
  if (fill.type === "SOLID") {
    return { type: "solid", color: extractColor(fill), opacity: fill.opacity };
  }
  if (fill.type === "GRADIENT_LINEAR" || fill.type === "GRADIENT_RADIAL") {
    return {
      type: fill.type === "GRADIENT_LINEAR" ? "linear-gradient" : "radial-gradient",
      stops: (fill.gradientStops ?? []).map((s) => ({
        color: extractColor({ color: s.color }),
        position: s.position,
      })),
    };
  }
  if (fill.type === "IMAGE") {
    return { type: "image", imageRef: fill.imageRef, scaleMode: fill.scaleMode };
  }
  return { type: fill.type };
}

function extractEffect(effect) {
  if (effect.type === "DROP_SHADOW" || effect.type === "INNER_SHADOW") {
    const c = extractColor({ color: effect.color });
    const inset = effect.type === "INNER_SHADOW" ? "inset " : "";
    const x = effect.offset?.x ?? 0;
    const y = effect.offset?.y ?? 0;
    const blur = effect.radius ?? 0;
    const spread = effect.spread ?? 0;
    return {
      type: effect.type === "DROP_SHADOW" ? "box-shadow" : "box-shadow-inset",
      css: `${inset}${x}px ${y}px ${blur}px ${spread}px ${c}`,
    };
  }
  if (effect.type === "LAYER_BLUR") {
    return { type: "blur", css: `blur(${effect.radius}px)` };
  }
  if (effect.type === "BACKGROUND_BLUR") {
    return { type: "backdrop-blur", css: `blur(${effect.radius}px)` };
  }
  return null;
}

function simplifyNode(node, depth = 0, maxDepth = Infinity) {
  const out = { id: node.id, name: node.name, type: node.type };

  // Dimensions
  if (node.size) {
    out.width = Math.round(node.size.x);
    out.height = Math.round(node.size.y);
  } else if (node.absoluteBoundingBox) {
    out.width = Math.round(node.absoluteBoundingBox.width);
    out.height = Math.round(node.absoluteBoundingBox.height);
  }

  // Sizing mode
  if (node.layoutSizingHorizontal) out.widthMode = node.layoutSizingHorizontal;
  if (node.layoutSizingVertical) out.heightMode = node.layoutSizingVertical;

  // Layout (auto-layout / flex)
  if (node.layoutMode) {
    const padding = extractPadding(node);
    out.layout = {
      mode: node.layoutMode,
      gap: node.itemSpacing ?? 0,
      ...(padding !== undefined && { padding }),
      justify: mapAxisAlign(node.primaryAxisAlignItems),
      align: mapAxisAlign(node.counterAxisAlignItems),
    };
    if (node.layoutWrap === "WRAP") out.layout.wrap = "wrap";
  }

  // Overflow
  if (node.clipsContent) out.overflow = "hidden";

  // Text
  if (node.type === "TEXT") {
    out.text = {
      content: node.characters,
      font: node.style?.fontFamily,
      weight: node.style?.fontWeight,
      size: node.style?.fontSize,
      lineHeight: extractLineHeight(node.style),
      align: node.style?.textAlignHorizontal?.toLowerCase(),
    };
    const ls = node.style?.letterSpacing;
    if (ls != null && ls !== 0) out.text.letterSpacing = ls;
    if (node.fills?.length) {
      const visible = node.fills.filter((f) => f.visible !== false);
      if (visible.length) out.text.color = extractColor(visible[0]);
    }
  }

  // Fills (non-text nodes)
  if (node.fills?.length && node.type !== "TEXT") {
    const visible = node.fills.filter((f) => f.visible !== false);
    if (visible.length) out.fills = visible.map(extractFill);
  }

  // Strokes
  if (node.strokes?.length) {
    const visible = node.strokes.filter((s) => s.visible !== false);
    if (visible.length) {
      out.strokes = visible.map((s) => ({
        ...extractFill(s),
        weight: node.strokeWeight ?? node.individualStrokeWeights,
        align: node.strokeAlign?.toLowerCase(),
      }));
    }
  }

  // Border radius
  if (node.rectangleCornerRadii) {
    const [tl, tr, br, bl] = node.rectangleCornerRadii;
    if (tl === tr && tr === br && br === bl) {
      if (tl > 0) out.borderRadius = tl;
    } else {
      out.borderRadius = `${tl} ${tr} ${br} ${bl}`;
    }
  } else if (node.cornerRadius != null && node.cornerRadius > 0) {
    out.borderRadius = node.cornerRadius;
  }

  // Opacity
  if (node.opacity != null && node.opacity !== 1) {
    out.opacity = parseFloat(node.opacity.toFixed(2));
  }

  // Effects
  if (node.effects?.length) {
    const visible = node.effects.filter((e) => e.visible !== false).map(extractEffect).filter(Boolean);
    if (visible.length) out.effects = visible;
  }

  // Component info
  if (node.componentId) out.componentId = node.componentId;
  if (node.componentProperties) out.componentProperties = node.componentProperties;

  // Children
  if (node.children && depth < maxDepth) {
    out.children = node.children.map((c) => simplifyNode(c, depth + 1, maxDepth));
  } else if (node.children?.length) {
    out.childCount = node.children.length;
  }

  return out;
}

// ─── Cache ───────────────────────────────────────────────────────────────────

const CACHE_TTL_MS = 30 * 60 * 1000; // 30 minutes

function cachePath(fileKey) {
  return join(tmpdir(), `figma-cache-${fileKey}.json`);
}

function readCache(fileKey) {
  try {
    const raw = JSON.parse(readFileSync(cachePath(fileKey), "utf8"));
    if (Date.now() - raw.timestamp < CACHE_TTL_MS) return raw.data;
  } catch {}
  return null;
}

function writeCache(fileKey, data) {
  writeFileSync(cachePath(fileKey), JSON.stringify({ timestamp: Date.now(), data }));
}

// ─── Commands ────────────────────────────────────────────────────────────────

async function cmdPages(flags) {
  const { apiKey, fileKey } = resolveConfig();

  if (!flags.fresh) {
    const cached = readCache(fileKey);
    if (cached) {
      console.log(JSON.stringify({ ok: true, cached: true, pages: cached }));
      return;
    }
  }

  const data = await figmaGet(`/files/${fileKey}?depth=2`, apiKey);

  const pages = data.document.children.map((page) => ({
    id: page.id,
    name: page.name,
    frames: (page.children ?? []).map((frame) => ({
      id: frame.id,
      name: frame.name,
      type: frame.type,
    })),
  }));

  writeCache(fileKey, pages);
  console.log(JSON.stringify({ ok: true, cached: false, pages }));
}

async function cmdChildren(nodeId, flags) {
  const { apiKey, fileKey } = resolveConfig();
  const depth = flags.depth ?? 1;
  const encoded = encodeURIComponent(nodeId);

  const data = await figmaGet(`/files/${fileKey}/nodes?ids=${encoded}&depth=${depth}`, apiKey);

  const nodeData = data.nodes[nodeId];
  if (!nodeData?.document) {
    fatal(`Node '${nodeId}' not found in file.`);
  }

  const doc = nodeData.document;
  const children = (doc.children ?? []).map((c) => simplifyNode(c, 0, depth - 1));

  console.log(
    JSON.stringify({
      ok: true,
      parentId: doc.id,
      parentName: doc.name,
      parentType: doc.type,
      children,
    })
  );
}

async function cmdNode(nodeId, flags) {
  const { apiKey, fileKey } = resolveConfig();
  const encoded = encodeURIComponent(nodeId);
  const geom = flags.geometry ? "&geometry=paths" : "";
  const depthParam = flags.depth != null ? `&depth=${flags.depth}` : "";

  const data = await figmaGet(
    `/files/${fileKey}/nodes?ids=${encoded}${depthParam}${geom}`,
    apiKey
  );

  const nodeData = data.nodes[nodeId];
  if (!nodeData?.document) {
    fatal(`Node '${nodeId}' not found in file.`);
  }

  const simplified = simplifyNode(nodeData.document, 0, flags.depth ?? Infinity);
  console.log(JSON.stringify({ ok: true, node: simplified }));
}

async function cmdDownloadImage(nodeId, outputPath, flags) {
  const { apiKey, fileKey } = resolveConfig();
  const scale = flags.scale ?? 2;
  const format = flags.format ?? "png";
  const encoded = encodeURIComponent(nodeId);

  // Step 1: Get the image URL from Figma
  const data = await figmaGet(
    `/images/${fileKey}?ids=${encoded}&format=${format}&scale=${scale}`,
    apiKey
  );

  const imageUrl = data.images?.[nodeId];
  if (!imageUrl) {
    fatal(`No image returned for node '${nodeId}'. The node may not be exportable.`);
  }

  // Step 2: Download the image (pre-signed S3 URL, no auth needed)
  const res = await fetch(imageUrl);
  if (!res.ok) {
    fatal(`Failed to download image: HTTP ${res.status}`);
  }

  // Step 3: Write to disk
  const absPath = resolve(outputPath);
  mkdirSync(dirname(absPath), { recursive: true });
  const buffer = Buffer.from(await res.arrayBuffer());
  await writeFile(absPath, buffer);

  console.log(
    JSON.stringify({
      ok: true,
      path: absPath,
      format,
      scale,
      nodeId,
      bytes: buffer.length,
    })
  );
}

// ─── CLI dispatch ────────────────────────────────────────────────────────────

function parseFlags(args) {
  const flags = {};
  const positional = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--fresh") {
      flags.fresh = true;
    } else if (args[i] === "--geometry") {
      flags.geometry = true;
    } else if (args[i] === "--depth" && args[i + 1]) {
      flags.depth = parseInt(args[i + 1], 10);
      i++;
    } else if (args[i] === "--scale" && args[i + 1]) {
      flags.scale = parseInt(args[i + 1], 10);
      i++;
    } else if (args[i] === "--format" && args[i + 1]) {
      flags.format = args[i + 1];
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
  case "pages":
    await cmdPages(flags);
    break;
  case "children":
    if (!positional[0]) fatal("Usage: node index.mjs children <nodeId> [--depth N]");
    await cmdChildren(positional[0], flags);
    break;
  case "node":
    if (!positional[0]) fatal("Usage: node index.mjs node <nodeId> [--depth N] [--geometry]");
    await cmdNode(positional[0], flags);
    break;
  case "download-image":
    if (!positional[0] || !positional[1])
      fatal("Usage: node index.mjs download-image <nodeId> <outputPath> [--scale N] [--format png|svg]");
    await cmdDownloadImage(positional[0], positional[1], flags);
    break;
  default:
    console.error(`Unknown command: ${command ?? "(none)"}`);
    console.error("Commands: pages, children, node, download-image");
    process.exit(1);
}
