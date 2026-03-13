---
name: commit-agent-changes
description: Identify the current agent's code changes, push them to a remote-only branch, and open a PR -- all without ever leaving the base branch. Use when the user says "commit my changes", "commit agent changes", "create a PR from this session", "push what you changed", or wants to turn the current agent's work into a pull request.
---

# Commit Agent Changes

Turn the current agent session's code changes into logically grouped commits on a remote-only branch with a pull request -- without ever switching the local branch. This keeps parallel agents working on the same base branch undisturbed.

## Workflow

Copy this checklist and track progress:

```
Commit Progress:
- [ ] Phase 1: Identify agent's changes
- [ ] Phase 2: Confirm with user and determine remote branch
- [ ] Phase 3: Group and commit
- [ ] Phase 4: Push, reset, and create PR
- [ ] Phase 5: Post-push cleanup (optional)
```

---

### Phase 1 -- Identify the Agent's Changes

Use a three-layer hybrid approach to build the definitive list of files this agent changed.

#### Step 1: Introspect conversation context

Review your own conversation history (already in your context window). List every file you wrote, edited, or deleted during this session. Include the operation type for each:

- `modified` -- edited an existing file (StrReplace)
- `new` -- created a file that didn't exist (Write to new path)
- `deleted` -- removed a file (Delete)

This is the primary source of truth.

#### Step 2: Parse transcript for validation

Find the agent-transcripts folder. Its path follows the pattern:

```
~/.cursor/projects/<project-slug>/agent-transcripts/
```

where `<project-slug>` is the workspace path with `/` replaced by `-` (e.g., `Users-timi-Documents-ngriid`).

List `.txt` files sorted by modification time (most recent first):

```bash
ls -t <transcripts-folder>/*.txt | head -5
```

Read the most recent `.txt` file and extract file paths from write-operation tool calls:

- `[Tool call] Write` -- look for the `path:` line
- `[Tool call] StrReplace` -- look for the `path:` line
- `[Tool call] Delete` -- look for the `path:` line

Ignore read-only tool calls (`Read`, `Grep`, `Glob`, `SemanticSearch`).

Merge any file paths found here that were missing from Step 1.

#### Step 3: Cross-reference with git

For each git repository in the workspace, run:

```bash
git status --porcelain
git diff --name-only
git diff --name-only --cached
```

Build the final change list: a file is included ONLY if it appears in BOTH the agent's list (Steps 1+2) AND git reports it as changed/untracked/deleted. This filters out pre-existing dirty state that the agent did not cause.

#### Step 4: Check for other uncommitted changes

Compare the agent's final file list against all dirty files reported by git. Any dirty file NOT in the agent's list belongs to another agent or pre-existing state. If such files exist, record them separately -- they will NOT be committed, but the user should be made aware of them in Phase 2 so they know other work is in progress.

Organize the final list by repository:

```
repo: <repo-name> (<repo-path>)
  modified: path/relative/to/repo
  new:      path/relative/to/repo
  deleted:  path/relative/to/repo
  (other uncommitted files not owned by this agent:)
    path/relative/to/repo
    path/relative/to/repo
```

If no files survive the intersection, inform the user that there are no uncommitted agent changes and stop.

---

### Phase 2 -- Confirm with User and Determine Remote Branch

#### Step 1: Identify the base branch

For each repository with changes, run:

```bash
git rev-parse --abbrev-ref HEAD
```

This is the **base branch** (e.g., `dev`, `main`). The agent stays on this branch throughout the entire operation.

#### Step 2: Generate the remote branch name

Determine the branch type from the nature of the changes:
- `feat/` -- new functionality
- `fix/` -- bug fix
- `refactor/` -- restructuring without behavior change
- `chore/` -- tooling, config, dependencies
- `docs/` -- documentation only

Generate a concise slug (3-5 words, kebab-case) summarizing the scope. The remote branch name follows the pattern `<type>/<slug>`. Examples:
- `refactor/remove-telemetry-caching`
- `feat/add-ingestion-buffer`
- `fix/mqtt-reconnect-handling`

Check if the generated name already exists on the remote:

```bash
git ls-remote --heads origin <type>/<slug>
```

If it exists, check for an open PR from that branch:

```bash
gh pr list --head <type>/<slug> --json number,title,url --jq '.[0]' 2>/dev/null
```

#### Step 3: Present the situation and confirm

Present the change list from Phase 1 to the user, along with the plan. Use `AskQuestion` to confirm.

The prompt varies by situation:

- **New remote branch**: "You're on `dev`. I'll commit your changes, push to remote branch `feat/add-buffer`, and open a PR against `dev`." Options: proceed, exclude files.
- **Existing remote branch with open PR**: "You're on `dev`. Remote branch `feat/add-buffer` already has PR #42. I'll force-push your latest changes to update it." Options: proceed, exclude files, create new branch instead.
- **Other uncommitted changes detected**: Additionally note: "Other uncommitted changes exist in this repo (not owned by this agent): {list}. These will NOT be included in your commit."

If the user excludes files, remove them from the list before continuing.

If changes span multiple repositories, confirm each repo separately. Each repo gets its own remote branch and PR.

#### Step 4: Verify remote state

For each repository, fetch the latest remote state:

```bash
git fetch origin
```

If fetch fails, abort and tell the user to check their network/auth.

After fetching, check whether the local base branch is ahead of its remote counterpart:

```bash
AHEAD=$(git rev-list --count origin/$BRANCH..HEAD)
```

If `AHEAD > 0`, warn the user: "Your local `{branch}` is {N} commit(s) ahead of `origin/{branch}`. These unpushed commits will be included in the PR." Options: abort (so the user can push or reset first), proceed anyway.

---

### Phase 3 -- Group and Commit

#### Save the base state

Before making any commits, record the current HEAD so the branch can be reset later:

```bash
BASE_HASH=$(git rev-parse HEAD)
```

#### Analyze and group

Read the diffs (`git diff -- <file>` for each file) and group them by cohesive concern. A "concern" is a single logical unit of work -- all the files needed to accomplish one thing.

**Grouping rules:**
- Files that implement the same feature or fix go together.
- A new utility/module AND the files that import it go in the same commit.
- Pure renames or moves are their own commit.
- Config/dependency changes are their own commit unless they directly enable a feature in the same PR.
- Deletions of replaced code go in the same commit as the replacement.

**Single commit when:** All changes serve one cohesive purpose.

**Multiple commits when:** The session's work spans distinct concerns (e.g., a refactor + a new feature + a config update). Split into one commit per concern.

#### Commit each group

Process groups in dependency order (foundational changes first, consuming code after).

For each group, first add any **new (untracked)** files from this group:

```bash
git add <new-file1> <new-file2>
```

Then commit using **pathspec** to include only this group's files:

```bash
git commit -m "$(cat <<'EOF'
type(scope): concise description

Optional body explaining WHY, not what. One short paragraph max.
EOF
)" -- <file1> <file2> <file3>
```

Using `git commit -- <files>` is critical: it stages and commits only the listed files, ignoring anything else in the staging area or working directory. This prevents one agent's commit from accidentally capturing another agent's staged changes.

**Commit message rules:**
- Subject line: `type(scope): description` -- under 72 characters
- `type` matches the branch prefix (feat, fix, refactor, chore, docs)
- `scope` is the module or area affected (e.g., `telemetry`, `mqtt`, `auth`)
- Body is optional; include only if the "why" isn't obvious from the subject
- Never reference the agent, AI, or Cursor in commit messages

---

### Phase 4 -- Push, Reset, and Create PR

#### Push to the remote-only branch

Push all commits (from `$BASE_HASH` to `HEAD`) to the remote branch. Use `--force-with-lease` to safely handle both new and existing remote branches:

```bash
git push --force-with-lease origin HEAD:refs/heads/<remote-branch>
```

If the push fails (e.g., due to a remote branch protection rule or lease conflict), inform the user and abort. Do NOT reset if the push failed.

#### Reset the local branch

Only after a successful push, reset the local branch back to its original state:

```bash
git reset $BASE_HASH
```

This is a mixed reset: the commit(s) are undone, but all working directory changes (from ALL agents) are preserved exactly as they were. The local base branch is back at the same commit it was on before the operation started.

#### Create or update the PR

**If an existing PR was found in Phase 2:**

The force-push already updated the PR. Display the existing PR URL to the user.

**If no existing PR was found:**

Create a new PR. Note: `--head` is the remote branch name (not a local branch):

```bash
gh pr create --head <remote-branch> --base <base-branch> --title "<title>" --body "$(cat <<'EOF'
## Summary

- <bullet 1: what changed and why>
- <bullet 2: what changed and why>
- <bullet 3 if needed>

## Test plan

- [ ] <specific verification step>
- [ ] <specific verification step>
EOF
)"
```

**PR title**: Same format as the commit subject if single-commit. For multi-commit PRs, write a broader summary (still under 72 chars).

**PR body rules:**
- Summary: 1-3 bullets focused on WHY, not WHAT
- Test plan: concrete steps someone can follow to verify the changes work

After creating the PR (or confirming the existing one was updated), display the PR URL to the user.

If changes spanned multiple repos, repeat Phases 3-4 for each repo.

---

### Phase 5 -- Post-Push Cleanup (Optional)

After a successful push and reset, the agent's files remain modified in the working directory (the reset preserved them). Offer to clean them up:

For **modified** files only this agent touched:

```bash
git checkout -- <file1> <file2>
```

This restores them to the base branch state. The changes are safe on the remote branch.

For **new** files this agent created:

```bash
rm <file1> <file2>
```

For **deleted** files: no cleanup needed (the file is already gone).

Ask the user before cleaning up: "Your changes are on remote branch `<branch>` and PR #N is open. Restore your modified files to the base state locally?" Options: clean up, keep dirty. Default to keeping them dirty (safest option).

---

## Important Principles

- **Never leave the base branch**: All commits are made on the base branch and pushed to remote-only refs. No local branches are created, no `git checkout -b`, no `git switch -c`.
- **Pathspec commits**: Always use `git commit -- <files>` to scope commits to specific files. This prevents staging area conflicts between concurrent agents.
- **Reset to a saved hash**: Always record `BASE_HASH=$(git rev-parse HEAD)` before committing and reset to it afterward. Never use relative resets like `HEAD~N`.
- **Push before reset**: Never reset until the push succeeds. If the push fails, the commits are still on the local branch and can be retried.
- **Only commit agent changes**: Never commit files the agent didn't touch, even if they have uncommitted changes.
- **Atomic commits**: Each commit should compile and make sense on its own. Don't commit half a refactor.
- **No AI references**: Commit messages, PR titles, PR bodies, and branch names should read as if a human wrote them. Never mention "agent", "AI", "Cursor", or "automated".
- **Respect existing conventions**: If the repo has a commit message convention or PR template, follow it instead of the defaults above.
- **Ask before acting**: Always confirm the file list, remote branch name, and base branch before creating any commits.
- **Report final state**: After creating the PR, run `git status` to confirm the working tree state and report it to the user.
