---
name: redeploy-frontend
description: Trigger a Vercel redeploy of the frontend by pushing a harmless comment change. Use when the user says "redeploy", "redeploy frontend", "trigger vercel deploy", or "trigger redeploy".
---

# Redeploy Frontend

Push a trivial timestamp comment change to the current deploy branch to trigger a Vercel redeploy. Uses a git worktree so the user's working directory is never touched -- works even with uncommitted local changes. Auto-detects the package manager, deploy branch, and target file. Auto-fixes prettier formatting issues before pushing.

## Workflow

### Step 0: Discover project config

Resolve the repo root and detect project settings before proceeding.

**Repo root:**
```bash
git rev-parse --show-toplevel
```
All subsequent commands run from this directory. Set `$REPO_ROOT` to this path.

**Repo name** -- derive `$REPO_NAME` from the directory name or git remote.

**Package manager** -- check for lock files at repo root:
- `pnpm-lock.yaml` → `pnpm`
- `yarn.lock` → `yarn`
- `bun.lockb` → `bun`
- `package-lock.json` → `npm`

If multiple lock files exist, prefer in the order listed above.

**Deploy branch** -- use the currently checked-out branch:
```bash
git branch --show-current
```
The user is responsible for being on the correct deploy branch before invoking this skill.

**Timestamp file** -- find the file to inject the redeploy comment into, in priority order:
1. Use your file-search tools (Grep) to find any `.ts` or `.tsx` file under `src/` or `app/` that contains the line `// redeploy:`. If found, that file is `$TIMESTAMP_FILE`.
2. Try common entry points in order: `src/app/layout.tsx`, `app/layout.tsx`, `src/main.tsx`, `src/App.tsx`, `src/index.ts`, `src/index.tsx`
3. If none of the above exist, ask the user: "Which file should I use to inject the redeploy timestamp comment?"

Set `$BRANCH`, `$PKG_MANAGER`, and `$TIMESTAMP_FILE` for use in all steps below. `$TIMESTAMP_FILE` is a path relative to the repo root.

---

### Step 1: Create a worktree for the deploy branch

Fetch the latest remote state and create a clean worktree at `origin/$BRANCH`:

```bash
git fetch origin
git worktree add ../$REPO_NAME-wt-redeploy origin/$BRANCH
```

Set `$DEPLOY_DIR` to the absolute path of the created worktree.

If the worktree path already exists (from a previous interrupted redeploy), remove it first:

```bash
git worktree remove ../$REPO_NAME-wt-redeploy --force
```

#### Handle unpushed local commits

Check if the user has local commits on `$BRANCH` that are not yet on the remote:

```bash
git rev-list --count origin/$BRANCH..HEAD
```

If ahead > 0 and the user is on `$BRANCH`, ask: "You have {N} unpushed commit(s) on `{branch}` not yet on the remote. Include them in the redeploy?"

If yes, capture the local tip and merge it into the worktree's detached HEAD:

```bash
LOCAL_TIP=$(git rev-parse $BRANCH)
git -C $DEPLOY_DIR merge $LOCAL_TIP --no-edit
```

Do NOT use `git -C $DEPLOY_DIR checkout $BRANCH` -- git forbids the same branch in two worktrees simultaneously, and the user's main worktree already has `$BRANCH` checked out. The worktree is on a detached HEAD (from `origin/$BRANCH`), so a merge incorporates the local commits without violating the one-branch-per-tree rule.

If no, continue with the worktree at `origin/$BRANCH`.

#### Sync build-essential non-tracked files

Copy non-version-controlled files needed for builds from the main repo to the worktree. These files are gitignored and therefore absent from a fresh worktree.

```bash
for f in .env .env.local .env.production .env.development .env.production.local .env.development.local .env.test .env.test.local; do
  [ -f "$REPO_ROOT/$f" ] && cp "$REPO_ROOT/$f" "$DEPLOY_DIR/$f"
done
```

For monorepos, also check subdirectories -- find all `.env*` files (excluding `node_modules` and `.git`) in `$REPO_ROOT` and copy them to the same relative paths in `$DEPLOY_DIR`:

```bash
find "$REPO_ROOT" -mindepth 2 -name '.env*' -not -path '*/node_modules/*' -not -path '*/.git/*' | while read src; do
  rel="${src#$REPO_ROOT/}"
  mkdir -p "$DEPLOY_DIR/$(dirname "$rel")"
  cp "$src" "$DEPLOY_DIR/$rel"
done
```

If the project has a `.env.example` or `.env.template` in the repo root but no `.env`, warn the user: "No `.env` file found. The build may fail if environment variables are required."

**Do not log or display the contents of these files** -- they may contain secrets.

### Step 2: Install dependencies

Install dependencies in the worktree so the build step works:

```bash
cd $DEPLOY_DIR
$PKG_MANAGER install
```

**Optimization:** For large projects where `install` is slow, you may symlink `node_modules` from the main worktree instead: `ln -s $REPO_ROOT/node_modules $DEPLOY_DIR/node_modules` (Unix) or `mklink /J $DEPLOY_DIR\node_modules $REPO_ROOT\node_modules` (Windows). This avoids a full install. Only do this if both worktrees are on the same branch and dependency versions match.

### Step 3: Local pre-build check and auto-fix

**All commands in this step run in `$DEPLOY_DIR`.**

Run the build locally to catch failures before pushing:

```bash
cd $DEPLOY_DIR
$PKG_MANAGER run build
```

**If the build passes**, continue to Step 4.

**If the build fails**, inspect the output:

- **Prettier-only failure** -- the output contains `[warn]` lines listing files and ends with `Code style issues found`. The build phase never ran. Auto-fix:

  ```bash
  cd $DEPLOY_DIR
  $PKG_MANAGER run format
  ```

  Then re-run `$PKG_MANAGER run build` to confirm the fix.
  - If the re-run **passes**, continue to Step 4. The formatted files will be staged alongside the timestamp change in Step 5.
  - If the re-run **fails** with a different error, treat as non-trivial (see below).

- **Non-trivial failure** (ESLint errors, TypeScript type errors, build errors) -- **abort**, clean up the worktree (Step 7), and report the full build output to the user. Ask follow-up questions about how to resolve before pushing.

### Step 4: Update the redeploy timestamp

Open `$DEPLOY_DIR/$TIMESTAMP_FILE`. Look for an existing line matching the pattern `// redeploy:`.

- If the line exists, **replace** it with a new UTC timestamp: `// redeploy: <timestamp>`
- If no such line exists, **insert** `// redeploy: <timestamp>` as the very first line of the file.

Generate the timestamp:
```bash
date -u +%Y-%m-%dT%H:%M:%SZ                                    # macOS/Linux/Git Bash
(Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")   # Windows PowerShell
```

Example result:
```typescript
// redeploy: 2026-03-05T14:23:00Z
// ... rest of file
```

### Step 5: Commit and push

**All commands in this step run in `$DEPLOY_DIR`.**

If prettier auto-fixed files in Step 3, stage everything and use the format-aware message:

```bash
cd $DEPLOY_DIR
git add .
git commit -m "chore: format and trigger redeploy"
git push origin $BRANCH
```

If no prettier fixes were needed (only the timestamp changed), stage just the timestamp file:

```bash
cd $DEPLOY_DIR
git add $TIMESTAMP_FILE
git commit -m "chore: trigger redeploy"
git push origin $BRANCH
```

### Step 6: Confirm

Report the push result to the user. Include the commit hash from the output.

### Step 7: Cleanup worktree

Remove the worktree:

```bash
git worktree remove ../$REPO_NAME-wt-redeploy
```

If removal fails, force it:

```bash
git worktree remove --force ../$REPO_NAME-wt-redeploy
```

This step runs after Step 6 on success, or after a build failure abort in Step 3.
