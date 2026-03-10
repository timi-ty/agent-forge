---
name: sync-skills
description: Sync locally installed Cursor agent skills to match a branch of the cursor-skills repo. Handles first-time installs and subsequent updates in one flow. Use when the user pastes a github.com/timi-ty/cursor-skills URL, or says "install skills", "update skills", "sync skills", or "install cursor skills".
---

# Sync Skills

Sync locally installed Cursor agent skills with a branch of the `cursor-skills` GitHub repo. Works for first-time installs (everything is new) and subsequent updates (adds new skills, updates changed ones, removes deleted ones). Always asks for confirmation before making changes.

## Dependencies

- `gh` CLI (GitHub CLI), authenticated

## Workflow

### Step 0: Parse the URL

Extract the `owner/repo` and `branch` from the URL the user pasted.

URL patterns:
- `https://github.com/{owner}/{repo}` → branch = `main`
- `https://github.com/{owner}/{repo}/tree/{branch}` → use the extracted branch
- `https://github.com/{owner}/{repo}/tree/{branch}/...` → use the extracted branch

Set `$OWNER`, `$REPO`, and `$BRANCH` for use in all steps below.

---

### Step 1: Fetch remote catalog

Fetch and decode `catalog.json` from the target branch:

```bash
gh api "repos/$OWNER/$REPO/contents/catalog.json?ref=$BRANCH" \
  --jq '.content | @base64d | fromjson'
```

Parse the `skills` array. Each entry has: `name`, `path`, `description`, `files`, `dependencies`, `notes`.

---

### Step 2: Discover installed skills

Check both scopes for installed skill folders:

**Global scope:**
- Windows: `%USERPROFILE%\.cursor\skills\`
- macOS/Linux: `~/.cursor/skills/`

**Workspace scope:**
- `.cursor/skills/` relative to the current working directory (only if this folder exists)

For each installed skill folder found, note its name and scope.

---

### Step 3: Diff remote vs installed

For each scope independently, classify every skill:

**NEW** — skill is in the remote catalog but not installed in this scope.

**UPDATED** — skill is installed in this scope AND exists in the remote catalog, but at least one file listed in the catalog entry's `files` array differs from its local counterpart. For each file in `files`, fetch the remote content and compare against the local file:

```bash
gh api "repos/$OWNER/$REPO/contents/{skill-path}/{file}?ref=$BRANCH" \
  --jq '.content | @base64d'
```

If any file differs (or does not exist locally), classify the skill as UPDATED.

**REMOVED** — skill folder exists locally in this scope but is NOT present in the remote catalog.

**UNCHANGED** — skill is installed and remote content matches local. Skip silently.

---

### Step 4: Present summary and confirm

Show a grouped diff for each scope that has changes. Example:

```
Global (~/.cursor/skills/):
  + sync-skills          [new]        requires: gh CLI
  ~ redeploy-frontend    [updated]
  - old-skill            [removed]

No workspace skills affected.
```

If there are NO changes in any scope, tell the user: "All installed skills are already up to date with `{branch}`." and stop.

**Confirmation for adds and updates:**
Ask once: "Apply these changes?" before proceeding with any adds or updates.

**Confirmation for removals:**
Ask separately for each skill to be removed: "Remove `{skill-name}` from {scope}? It is no longer in the remote catalog." Only remove if the user confirms.

**Scope for new skills:**
If a new skill is detected and the workspace scope (`.cursor/skills/`) is not present in the current directory, default to global. If it exists, ask the user: "Install `{skill-name}` globally or workspace-only?"

---

### Step 5: Execute

Clone the remote branch to a temporary directory to get all skill files (not just `SKILL.md`):

```bash
# Use gh to clone only the skills folder at the target branch
git clone --depth 1 --branch $BRANCH https://github.com/$OWNER/$REPO.git <tmp-dir>
```

If the clone fails, **abort** and tell the user: "Could not clone `{owner}/{repo}` at branch `{branch}`. Verify the URL and that the branch exists."

Then apply confirmed changes:

**For each REMOVED skill (confirmed):**
```bash
Remove-Item "<scope-path>\{skill-name}" -Recurse -Force   # Windows
rm -rf <scope-path>/{skill-name}                          # macOS/Linux
```

**For each NEW or UPDATED skill (confirmed):**
```bash
# Windows — remove first to avoid nesting into an existing folder
Remove-Item "<scope-path>\{skill-name}" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "<tmp-dir>\{skill-path}" "<scope-path>\{skill-name}" -Recurse -Force

# macOS/Linux — remove first to avoid nesting into an existing folder
rm -rf <scope-path>/{skill-name}
cp -r <tmp-dir>/{skill-path} <scope-path>/{skill-name}
```

Clean up the temp directory after all changes are applied.

---

### Step 6: Report

List every change applied, grouped by scope and action:

```
Applied:
  Global:
    + sync-skills installed
    ~ redeploy-frontend updated
    - old-skill removed

Reminder: Start a new Cursor agent session for skill changes to take effect.
```

If any changes were skipped (user declined), list them as skipped.
