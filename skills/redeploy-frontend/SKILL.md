---
name: redeploy-frontend
description: Trigger a Vercel redeploy of the frontend by pushing a harmless comment change. Use when the user says "redeploy", "redeploy frontend", "trigger vercel deploy", or "trigger redeploy".
---

# Redeploy Frontend

Push a trivial timestamp comment change to the current deploy branch to trigger a Vercel redeploy. Auto-detects the package manager, deploy branch, and target file. Auto-fixes prettier formatting issues before pushing.

## Workflow

### Step 0: Discover project config

Resolve the repo root and detect project settings before proceeding.

**Repo root:**
```bash
git rev-parse --show-toplevel
```
All subsequent commands run from this directory.

**Package manager** -- check for lock files at repo root:
- `pnpm-lock.yaml` → `pnpm`
- `yarn.lock` → `yarn`
- `bun.lockb` → `bun`
- `package-lock.json` → `npm`

If multiple lock files exist, prefer in the order listed above.

**Deploy branch** — use the currently checked-out branch:
```bash
git branch --show-current
```
The user is responsible for being on the correct deploy branch before invoking this skill.

**Timestamp file** -- find the file to inject the redeploy comment into, in priority order:
1. Use your file-search tools (Grep) to find any `.ts` or `.tsx` file under `src/` or `app/` that contains the line `// redeploy:`. If found, that file is `$TIMESTAMP_FILE`.
2. Try common entry points in order: `src/app/layout.tsx`, `app/layout.tsx`, `src/main.tsx`, `src/App.tsx`, `src/index.ts`, `src/index.tsx`
3. If none of the above exist, ask the user: "Which file should I use to inject the redeploy timestamp comment?"

Set `$BRANCH`, `$PKG_MANAGER`, and `$TIMESTAMP_FILE` for use in all steps below.

---

### Step 1: Ensure clean working tree

```bash
git status --porcelain
```

If there is any output, **abort** and tell the user:

> "There are uncommitted changes in this repo. Stash or commit them before redeploying."

### Step 2: Verify remote branch state

Fetch the latest remote state (without merging):

```bash
git fetch origin
```

Compute the ahead/behind relationship:

```bash
git rev-list --count HEAD..origin/$BRANCH   # commits behind
git rev-list --count origin/$BRANCH..HEAD   # commits ahead
```

Act on the result:

- **Up to date** (both = 0): continue.
- **Behind only** (behind > 0, ahead = 0): ask the user: "Your branch is {N} commit(s) behind `origin/{branch}`. Fast-forward before proceeding?" If yes, run `git pull --ff-only origin $BRANCH` and continue. If no, abort.
- **Ahead only** (behind = 0, ahead > 0): warn the user: "You have {N} unpushed commit(s) on `{branch}`. Proceed anyway?" If yes, continue. If no, abort.
- **Diverged** (both > 0): **abort** and tell the user: "Local `{branch}` has diverged from `origin/{branch}` ({N} ahead, {M} behind). Resolve the divergence manually before proceeding."

### Step 3: Local pre-build check and auto-fix

Run the build locally to catch failures before pushing:

```bash
$PKG_MANAGER run build
```

**If the build passes**, continue to Step 4.

**If the build fails**, inspect the output:

- **Prettier-only failure** -- the output contains `[warn]` lines listing files and ends with `Code style issues found`. The `next build` phase never ran. Auto-fix:

  ```bash
  $PKG_MANAGER run format
  ```

  Then re-run `$PKG_MANAGER run build` to confirm the fix.
  - If the re-run **passes**, continue to Step 4. The formatted files will be staged alongside the timestamp change in Step 5.
  - If the re-run **fails** with a different error, treat as non-trivial (see below).

- **Non-trivial failure** (ESLint errors, TypeScript type errors, build errors) -- **abort** and report the full build output to the user. Ask follow-up questions about how to resolve before pushing.

### Step 4: Update the redeploy timestamp

Open `$TIMESTAMP_FILE`. Look for an existing line matching the pattern `// redeploy: `.

- If the line exists, **replace** it with a new UTC timestamp: `// redeploy: <timestamp>`
- If no such line exists, **insert** `// redeploy: <timestamp>` as the very first line of the file.

Generate the timestamp:
```bash
date -u +%Y-%m-%dT%H:%M:%SZ
```

Example result:
```typescript
// redeploy: 2026-03-05T14:23:00Z
import type { Metadata } from "next";
```

### Step 5: Commit and push

If prettier auto-fixed files in Step 3, stage everything and use the format-aware message:

```bash
git add .
git commit -m "chore: format and trigger redeploy"
git push origin $BRANCH
```

If no prettier fixes were needed (only the timestamp changed), stage just the timestamp file:

```bash
git add $TIMESTAMP_FILE
git commit -m "chore: trigger redeploy"
git push origin $BRANCH
```

### Step 6: Confirm

Report the push result to the user. Include the commit hash from the output.
