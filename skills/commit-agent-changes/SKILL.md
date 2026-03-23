---
name: commit-agent-changes
description: Identify the current agent's code changes, create a branch, group changes into logical commits, and open a PR. Use when the user says "commit my changes", "commit agent changes", "create a PR from this session", "push what you changed", or wants to turn the current agent's work into a pull request.
---

# Commit Agent Changes

Turn the current agent session's code changes into a well-structured branch with logically grouped commits and a pull request.

## Workflow

Copy this checklist and track progress:

```
Commit Progress:
- [ ] Phase 1: Identify agent's changes
- [ ] Phase 2: Detect branch state and confirm with user
- [ ] Phase 3: Branch out via worktree (skip if already on feature branch)
- [ ] Phase 4: Group and commit
- [ ] Phase 5: Push (and create PR if needed)
- [ ] Phase 6: Cleanup worktree and local changes
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

#### Step 2: Parse transcript for validation (Cursor only)

> **Skip this step if running in Claude Code.** Claude Code does not maintain agent transcripts. The conversation context (Step 1) and git state (Step 3) provide sufficient coverage.

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

### Phase 2 -- Detect Branch State and Confirm with User

#### Step 1: Detect the current branch

For each repository with changes, run:

```bash
git rev-parse --abbrev-ref HEAD
```

Classify the result:
- **Default branch** (`main`, `master`, `develop`) -- a new feature branch is needed (Phase 3 will run).
- **Feature branch** (anything else) -- already on the right branch (Phase 3 will be skipped).

When on a feature branch, check for an existing open PR:

```bash
gh pr view --json number,title,url,baseRefName 2>/dev/null
```

Record three pieces of state per repo for use in later phases:
- `on_feature_branch`: boolean
- `existing_pr`: `{number, title, url, baseRefName}` or null
- `base_branch`: from the existing PR's `baseRefName`, or to be asked

#### Step 2: Present the situation and confirm

Present the change list from Phase 1 to the user, along with the detected branch state. Ask the user to confirm.

The prompt varies by situation:

- **On a feature branch with an existing PR**: "You're on `refactor/remove-caching` which has PR #42 open against `main`. Commit and push to it?" Options: proceed, exclude files.
- **On a feature branch with no PR**: "You're on `feat/ingestion-buffer` with no open PR. Commit, push, and create a new PR?" Options: proceed, exclude files. Also ask for the **base branch** (present the repo's default branch as the default option).
- **On a default branch**: "You're on `main`. I'll create a new feature branch." Options: proceed, exclude files. Ask for the **base branch** (present `main` as the default).

If other uncommitted changes were detected in Phase 1 Step 4, additionally note: "Other uncommitted changes exist in this repo (not owned by this agent): {list}. These will NOT be included."

If the user excludes files, remove them from the list before continuing.

#### Step 3: Verify remote branch state

Set `$BRANCH` to the current branch name (result of `git rev-parse --abbrev-ref HEAD` from Step 1).

For each repository, fetch the latest remote state (without merging):

```bash
git fetch origin
```

Compute the ahead/behind relationship against the current branch (`$BRANCH`):

```bash
git rev-list --count HEAD..origin/$BRANCH   # commits behind
git rev-list --count origin/$BRANCH..HEAD   # commits ahead
```

Act on the result:

- **Up to date** (both = 0): continue.
- **Behind only** (behind > 0, ahead = 0): ask the user: "Your branch is {N} commit(s) behind `origin/{branch}`. Fast-forward before proceeding?" If yes, run `git pull --ff-only origin $BRANCH` and continue. If no, abort.
- **Ahead only** (behind = 0, ahead > 0): this is expected if there are already commits on the branch. Inform the user: "You have {N} existing commit(s) on `{branch}` not yet pushed. New commits will be added on top." Continue.
- **Diverged** (both > 0): **abort** and tell the user: "Local `{branch}` has diverged from `origin/{branch}` ({N} ahead, {M} behind). Resolve the divergence manually before proceeding."

**Note (applies to all of Phase 2):** If changes span multiple repositories, confirm each repo separately. Each repo gets its own branch and PR.

---

### Phase 3 -- Branch Out via Worktree

**Skip this phase entirely if `on_feature_branch` is true for the repo.** When skipped, set `$COMMIT_DIR` to the current workspace root and proceed directly to Phase 4.

For each repository that is on a default branch:

#### Step 1: Determine branch name

1. **Determine the branch type** from the nature of the changes:
   - `feat/` -- new functionality
   - `fix/` -- bug fix
   - `refactor/` -- restructuring without behavior change
   - `chore/` -- tooling, config, dependencies
   - `docs/` -- documentation only

2. **Generate a concise slug** (3-5 words, kebab-case) summarizing the scope. Examples:
   - `refactor/remove-telemetry-caching`
   - `feat/add-ingestion-buffer`
   - `fix/mqtt-reconnect-handling`

If the branch name already exists, append a short numeric suffix (e.g., `-2`).

#### Step 2: Create the worktree

Determine `$REPO_NAME` from the git remote or directory name. Create a worktree with the new branch based on the current HEAD:

```bash
git worktree add -b <branch-name> ../$REPO_NAME-wt-commit HEAD
```

Set `$COMMIT_DIR` to the absolute path of the created worktree.

If the worktree path already exists (from a previous interrupted commit), remove it first:

```bash
git worktree remove ../$REPO_NAME-wt-commit --force
```

#### Step 3: Transfer the agent's changes to the worktree

Only the agent's changes (from the Phase 1 change list) are transferred. The user's working directory is not modified.

**Modified files** (tracked files with changes):

```bash
git diff -- <file1> <file2> ... > agent-changes.patch
```

Then apply in the worktree:

```bash
git -C $COMMIT_DIR apply <absolute-path-to>/agent-changes.patch
```

Delete the temporary patch file after applying.

If `git apply` fails (e.g., binary files, complex renames, encoding issues), fall back to direct file copy for the affected files: copy each failed file from the workspace root to the corresponding path in `$COMMIT_DIR`, overwriting the base-branch version.

**New files** (untracked):

Copy each new file to the corresponding path in `$COMMIT_DIR`, creating parent directories as needed.

**Deleted files**:

Remove each deleted file in `$COMMIT_DIR`.

After transfer, verify that `git -C $COMMIT_DIR status --porcelain` shows the expected changes.

---

### Phase 4 -- Group and Commit

**All git commands in this phase run in `$COMMIT_DIR`** (the worktree if Phase 3 created one, or the workspace root if Phase 3 was skipped). Use `git -C $COMMIT_DIR` or set the working directory to `$COMMIT_DIR` before running commands.

#### Analyze and group

Read the diffs (`git -C $COMMIT_DIR diff -- <file>` for each file) and group them by cohesive concern. A "concern" is a single logical unit of work -- all the files needed to accomplish one thing.

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
git -C $COMMIT_DIR add <new-file1> <new-file2>
```

Then commit using **pathspec** to include only this group's files:

```bash
git -C $COMMIT_DIR commit -m "$(cat <<'EOF'
type(scope): concise description

Optional body explaining WHY, not what. One short paragraph max.
EOF
)" -- <file1> <file2> <file3>
```

Using `git commit -- <files>` stages and commits only the listed files. Even though the worktree should only contain agent changes, pathspec provides defense-in-depth against unexpected files (e.g., leftover artifacts from a failed patch apply).

**Commit message rules:**
- Subject line: `type(scope): description` -- under 72 characters
- `type` matches the branch prefix (feat, fix, refactor, chore, docs)
- `scope` is the module or area affected (e.g., `telemetry`, `mqtt`, `auth`)
- Body is optional; include only if the "why" isn't obvious from the subject
- Never reference the agent, AI, Cursor, or Claude Code in commit messages

---

### Phase 5 -- Push (and Create PR if Needed)

**All git commands in this phase run in `$COMMIT_DIR`** (same as Phase 4).

Push the commits:

```bash
git -C $COMMIT_DIR push -u origin HEAD
```

#### If an existing PR was found in Phase 2

The push is sufficient -- the PR is already open and will reflect the new commits. Display the existing PR URL to the user.

#### If no existing PR was found

Create a new PR (run `gh` from within `$COMMIT_DIR` so it picks up the correct branch):

```bash
cd $COMMIT_DIR
gh pr create --base <base-branch> --title "<title>" --body "$(cat <<'EOF'
## Summary

- <bullet 1: what changed and why>
- <bullet 2: what changed and why>
- <bullet 3 if needed>

## Commits

- `<hash-short>` type(scope): description
- `<hash-short>` type(scope): description

## Test plan

- [ ] <specific verification step>
- [ ] <specific verification step>
EOF
)"
```

**PR title**: Same format as the commit subject if single-commit. For multi-commit PRs, write a broader summary (still under 72 chars).

**PR body rules:**
- Summary: 1-3 bullets focused on WHY, not WHAT
- Commits: list each commit hash + message (get from `git log --oneline <base>..HEAD`)
- Test plan: concrete steps someone can follow to verify the changes work

After pushing (or creating a PR), display the PR URL to the user.

If changes spanned multiple repos, repeat Phases 3-6 for each repo.

---

### Phase 6 -- Cleanup Worktree and Local Changes

**Skip this phase if Phase 3 was skipped** (i.e., `on_feature_branch` was true and no worktree was created).

#### Step 1: Remove the worktree

```bash
git worktree remove ../$REPO_NAME-wt-commit
```

If removal fails, force it:

```bash
git worktree remove --force ../$REPO_NAME-wt-commit
```

#### Step 2: Clean up local changes

The agent's changes still exist as uncommitted modifications in the user's original working directory. Since they are now committed and pushed in the PR, ask the user whether to revert them locally.

Ask the user with these options:

- **Clean up** -- revert the agent's changes in the working directory (recommended). This restores the working directory to a clean state.
- **Keep locally** -- leave the changes in the working directory as-is. Useful if the user wants to keep iterating on them.

**If "Clean up" is selected:**

For modified files:
```bash
git checkout -- <file1> <file2> ...
```

For new (untracked) files:
```bash
rm <file1> <file2> ...
```

For deleted files -- no action needed; the file is already absent locally, and the deletion is captured in the PR.

**If "Keep locally" is selected:** Do nothing. Inform the user that the local changes remain uncommitted.

#### Step 3: Verify

Run `git status` in the original working directory to confirm the expected state and report it to the user.

---

## Important Principles

- **Only commit agent changes**: Never commit files the agent didn't touch, even if they have uncommitted changes.
- **Atomic commits**: Each commit should compile and make sense on its own. Don't commit half a refactor.
- **No AI references**: Commit messages, PR titles, and PR bodies should read as if a human wrote them. Never mention "agent", "AI", "Cursor", "Claude Code", or "automated".
- **Respect existing conventions**: If the repo has a commit message convention or PR template, follow it instead of the defaults above.
- **Ask before acting**: Always confirm the file list and base branch before creating any commits.
- **Never disturb the user's branch**: When on a default branch, use a worktree to create the feature branch. The user's working directory stays on its original branch throughout.
- **Clean state**: After creating the PR, run `git status` to confirm the expected state. Report any leftover uncommitted changes to the user.
