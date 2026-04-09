---
name: code-review
description: Perform a senior-engineer code review of a pull request. Checks that changes are scoped to the PR's stated goal, conform to existing codebase patterns, introduce no bugs, are maximally efficient, and contain no dead or unused code. Use when the user asks to review a PR, code review, review pull request, or attaches a PR link/URL.
---

# Code Review

Perform a thorough, senior-engineer-level code review of a pull request.

## Review Goals

1. **Scope** -- Every changed file must relate to the PR's stated purpose. No unrelated changes, no scope creep, no accidental inclusions from a dirty branch.
2. **Conformance** -- New code must match the patterns, conventions, and architecture of the existing codebase exactly.
3. **Correctness** -- No new bugs, no missing edge cases, no logic errors.
4. **Efficiency** -- Code is as lean and performant as possible; no redundant operations.
5. **No dead code** -- Every import, variable, function, and branch is used.

---

## Workflow

Copy this checklist and track progress:

```
Review Progress:
- [ ] Phase 1: Gather PR context (metadata, diff, linked issues)
- [ ] Phase 2: PR scope & hygiene check
- [ ] Phase 3: Understand existing codebase patterns (via worktree)
- [ ] Phase 4: File-by-file diff review
- [ ] Phase 5: Cross-cutting analysis
- [ ] Phase 6: Deliver structured report
- [ ] Phase 7: Determine verdict
- [ ] Phase 8: Confirm verdict with user
- [ ] Phase 9: Apply verdict
- [ ] Phase 10: Offer to merge (approve path only)
- [ ] Phase 11: Cleanup worktrees
```

### Phase 1 -- Gather PR Context

Extract the PR identifier from the user's message. It may be:
- A full GitHub URL (e.g. `https://github.com/owner/repo/pull/123`)
- An owner/repo#number reference (e.g. `owner/repo#123`)
- A PR number with repo context already known

Then fetch the PR data using the `gh` CLI:

```bash
# Get PR metadata
gh pr view <PR> --repo <owner/repo> --json title,body,files,additions,deletions,changedFiles,baseRefName,headRefName

# Get the full diff
gh pr diff <PR> --repo <owner/repo>
```

If the system prompt also contains an `<attached_pull_requests>` section with a folder path, you may additionally read `summary.json`, `all.diff`, and per-file diffs from that folder as supplementary data.

After gathering, list every changed file and categorize each as **added**, **modified**, or **deleted**.

#### Fetch linked issues

Parse the PR body for linked issues. Look for:
- Keywords: `Fixes #N`, `Closes #N`, `Resolves #N` (and their variations)
- Issue URLs: `https://github.com/owner/repo/issues/N`
- Any `#N` or `owner/repo#N` references

For each linked issue, fetch its context:

```bash
gh issue view <N> --repo <owner/repo> --json title,body,labels
```

Store the issue title, body, and labels. This defines the **intended scope** of the PR and is used in Phase 2 for scope validation.

If no linked issue is found, note this as a potential PR hygiene concern (PRs should link to their motivating issue).

### Phase 2 -- PR Scope & Hygiene Check

Before reading any code, evaluate whether the PR's changes match its stated purpose. This phase catches problems that no amount of code-level review can detect: unrelated files, scope creep, and accidental inclusions from a dirty branch.

1. **Title-diff alignment**: Read the PR title and body. Read the list of changed files. Ask: does every changed file plausibly relate to what the title and body describe? Flag files that appear unrelated (e.g., packaging files in a CI/CD PR, config changes in a feature PR).

2. **Issue-scope alignment**: If a linked issue was fetched in Phase 1, compare the issue's description against the changed files. Flag changes that fall outside the issue's stated scope.

3. **PR body completeness**: Check that the PR body exists and is non-empty. A PR with no description is a hygiene issue.

4. **Accidental inclusion detection**: Look for patterns that suggest dirty-branch contamination:
   - Files in completely unrelated directories
   - Changes to files the PR description never mentions or implies
   - A mix of unrelated concerns (e.g., a feature PR that also modifies unrelated infrastructure)

Record all findings. Scope issues are reported in Phase 6 and contribute to the verdict:
- **High**: Files that clearly don't belong (accidental inclusions from a wrong branch) -- these would ship unreviewed, unintended changes if merged.
- **Medium**: Missing PR description, no linked issue, weak title-diff alignment, missing test coverage for behavioral changes.
- **Low**: Minor scope concerns that are judgment calls.

### Phase 3 -- Understand Existing Codebase Patterns

#### Step 0: Create a worktree for the base branch

Create an isolated worktree checked out to the latest remote base branch. This avoids touching the user's working directory and guarantees pattern reads come from the true base branch state regardless of what is currently checked out locally.

Set `$BRANCH` to the base branch name (`baseRefName` from Phase 1). Determine the repo name from the git remote or directory name and set `$REPO_NAME`. Set `$REVIEW_BASE` to the worktree path.

```bash
git fetch origin
git worktree add ../$REPO_NAME-wt-review-pr<N> origin/$BRANCH
```

Set `$REVIEW_BASE` to the absolute path of the created worktree (e.g., `../<repo>-wt-review-pr<N>`).

If the worktree path already exists (e.g., from a previous interrupted review), remove it first:

```bash
git worktree remove ../$REPO_NAME-wt-review-pr<N> --force
```

#### Sync build-essential non-tracked files

Copy non-version-controlled files needed for builds from the main repo to the worktree. These files are gitignored and therefore absent from a fresh worktree.

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
for f in .env .env.local .env.production .env.development .env.production.local .env.development.local .env.test .env.test.local; do
  [ -f "$REPO_ROOT/$f" ] && cp "$REPO_ROOT/$f" "$REVIEW_BASE/$f"
done
```

For monorepos, also check subdirectories -- find all `.env*` files (excluding `node_modules` and `.git`) in `$REPO_ROOT` and copy them to the same relative paths in the worktree:

```bash
find "$REPO_ROOT" -mindepth 2 -name '.env*' -not -path '*/node_modules/*' -not -path '*/.git/*' | while read src; do
  rel="${src#$REPO_ROOT/}"
  mkdir -p "$REVIEW_BASE/$(dirname "$rel")"
  cp "$src" "$REVIEW_BASE/$rel"
done
```

If the project has a `.env.example` or `.env.template` in the repo root but no `.env`, warn the user: "No `.env` file found. The build may fail if environment variables are required."

**Do not log or display the contents of these files** -- they may contain secrets.

#### Optional: Check out the PR head branch

If you need to run the PR code locally (build, test, lint), also create a worktree for the PR's head:

```bash
git fetch origin pull/<N>/head:pr-<N>
git worktree add ../$REPO_NAME-wt-review-pr<N>-head pr-<N>
```

This is not required for every review. Use it when deeper verification (running builds/tests) is needed.

#### Sync build-essential non-tracked files

If the PR head worktree was created, copy non-version-controlled files needed for builds from the main repo to the worktree. These files are gitignored and therefore absent from a fresh worktree. Set `$HEAD_WT` to the PR head worktree path.

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
HEAD_WT=../$REPO_NAME-wt-review-pr<N>-head
for f in .env .env.local .env.production .env.development .env.production.local .env.development.local .env.test .env.test.local; do
  [ -f "$REPO_ROOT/$f" ] && cp "$REPO_ROOT/$f" "$HEAD_WT/$f"
done
```

For monorepos, also check subdirectories -- find all `.env*` files (excluding `node_modules` and `.git`) in `$REPO_ROOT` and copy them to the same relative paths in the worktree:

```bash
find "$REPO_ROOT" -mindepth 2 -name '.env*' -not -path '*/node_modules/*' -not -path '*/.git/*' | while read src; do
  rel="${src#$REPO_ROOT/}"
  mkdir -p "$HEAD_WT/$(dirname "$rel")"
  cp "$src" "$HEAD_WT/$rel"
done
```

If the project has a `.env.example` or `.env.template` in the repo root but no `.env`, warn the user: "No `.env` file found. The build may fail if environment variables are required."

**Do not log or display the contents of these files** -- they may contain secrets.

---

This is the most critical phase. You cannot review code without knowing what "correct" looks like in this codebase.

**All file reads in this phase use the `$REVIEW_BASE` worktree path**, not the workspace root. This guarantees you are reading the base branch state.

For each changed file:
1. **Read the full current file** from `$REVIEW_BASE` (not just the diff) to understand the surrounding context.
2. **Read 2-3 sibling files** from `$REVIEW_BASE` in the same directory or module to identify:
   - Naming conventions (files, functions, variables, types)
   - Architectural patterns (how modules are structured, how exports are organized)
   - Error handling style (try/catch patterns, error types, Result types)
   - Typing conventions (interfaces vs types, generics usage, strictness level)
   - Import organization and ordering
   - Comment and documentation style

For large PRs (10+ files), use parallel explore subagents to investigate different areas of the codebase concurrently. Launch up to 4 at a time, each exploring a different module or directory touched by the PR.

Take notes on the patterns you discover. You will use these as the baseline for Phase 4.

### Phase 4 -- File-by-File Diff Review

For each changed file, read its individual diff and review against the detailed checklist.

For the full review checklist, see [checklist.md](checklist.md).

Key review areas (summarized):

- **Scope**: Does this file belong in this PR? (Cross-reference against Phase 2 findings.)
- **Pattern conformance**: Does the new code follow the exact same patterns found in Phase 3? Naming, structure, error handling, types, imports?
- **Correctness**: Any bugs? Missing null checks? Off-by-one errors? Unhandled promise rejections? Race conditions?
- **Efficiency**: Any unnecessary allocations, redundant computations, N+1 patterns, or operations that could be batched?
- **Dead code**: Any unused imports, unreachable branches, variables assigned but never read, commented-out code, functions defined but never called?
- **Type safety**: Are types as narrow as possible? Any `any` that should be typed? Missing generics?

When you find an issue, note the exact file path and line number from the diff.

### Phase 5 -- Cross-Cutting Analysis

After reviewing individual files, check for issues that span the whole PR:

- **New dependencies**: Are they justified? Are versions pinned?
- **Internal consistency**: Do all files in the PR follow the same conventions as each other?
- **Security**: Exposed secrets, injection vectors, auth bypasses, unsanitized input?
- **Performance**: Unbounded loops, missing pagination, expensive operations in hot paths?
- **API contract changes**: Do changes to interfaces/types/APIs break any consumers?
- **Missing changes (interface consumers)**: Are there files that *should* have been changed but weren't? (e.g., updating an interface without updating its consumers)
- **Missing changes (test coverage)**: Do behavioral changes have corresponding test additions or modifications?
- **Unrelated changes**: Confirm any files flagged in Phase 2 as potentially out-of-scope. After reading the code, do they genuinely relate to the PR's purpose, or are they accidental inclusions?

### Phase 6 -- Output

Write a markdown file to the workspace root named `pr-{number}-review.md` (e.g. `pr-32-review.md`).

**Rules for the output:**
- Include ONLY items that require changes. Do not include praise, compliments, "looks good" notes, or things that are already correct.
- Each item is a concise, direct bullet point. One or two sentences max. State the problem and the fix.
- Group items under `### High`, `### Medium`, and `### Low` priority headings.
- If a priority group has no items, omit that heading entirely.
- Reference specific file paths (and line numbers when useful) in bold at the start of each bullet.

**Priority definitions:**
- **High** -- Bugs, data loss, security holes, dead code that misleads users, or fundamentally broken behavior. Must fix before merge.
- **Medium** -- Deviations from codebase patterns, inconsistencies, maintainability concerns. Should fix.
- **Low** -- Minor optimizations, nitpicks, optional improvements. Nice to fix.

**Output template:**

```markdown
## PR #[number] Review

### High

- **`path/to/file.ts`** -- [Concise description of problem. How to fix it.]

### Medium

- **`path/to/file.ts`** -- [Concise description. Suggestion.]

### Low

- **`path/to/file.ts`** -- [Concise description.]
```

After writing the file, display the contents to the user as well.

### Phase 7 -- Verdict

Based on the review report, determine your verdict:

- **Request Changes** -- if there are any **High** or **Medium** priority items.
- **Approve** -- only if there are zero High and zero Medium items (Low-only or no issues at all).

State the verdict clearly to the user along with a one-sentence rationale (e.g., "Requesting changes because there are 2 High-priority bugs and 1 Medium-priority pattern deviation." or "Approving -- no blocking issues found, only minor Low-priority suggestions.").

### Phase 8 -- Confirm Verdict with User

Ask the user to confirm or override the verdict. Offer these options:

- **Go ahead** -- post the review verdict (approve or request-changes) to GitHub. This does **not** merge the PR.
- **Plan to address issues** -- (only shown when verdict is Request Changes) switch to plan mode and create a plan to fix the issues found in the review.
- **Switch to Approve** -- (only shown when verdict is Request Changes) override and approve instead.
- **Switch to Request Changes** -- (only shown when verdict is Approve) override and request changes instead.
- **Other** -- the user wants to proceed differently. If selected, ask the user to describe how they want to proceed and follow their instructions.

Do not proceed until the user responds.

#### If "Plan to address issues" is selected

Ask a follow-up question to determine scope. Offer these options:

- **All issues** -- plan to address every issue from the review report (High, Medium, and Low).
- **Exclude specific issues** -- address all issues except ones the user specifies. If selected, ask the user to input the issue numbers to omit (referencing the numbered items from the review report).
- **Include specific issues only** -- address only the issues the user specifies. If selected, ask the user to input the issue numbers to include.

Once the scope is determined, switch to plan mode and create a plan with one actionable todo per selected issue, referencing the file path and fix description from the review report. Do **not** apply the PR verdict (no approve or request-changes is posted) -- the user can re-run the review or manually apply the verdict after fixes are made.

**Applying fixes to the PR branch**: When you exit plan mode and implement the fixes, use a worktree checked out to the PR's **head branch** (not the base branch):

```bash
git worktree add ../$REPO_NAME-wt-fix-pr<N> <headRefName>
```

#### Sync build-essential non-tracked files

Copy non-version-controlled files needed for builds from the main repo to the fix worktree. These files are gitignored and therefore absent from a fresh worktree. Set `$FIX_WT` to the fix worktree path.

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
FIX_WT=../$REPO_NAME-wt-fix-pr<N>
for f in .env .env.local .env.production .env.development .env.production.local .env.development.local .env.test .env.test.local; do
  [ -f "$REPO_ROOT/$f" ] && cp "$REPO_ROOT/$f" "$FIX_WT/$f"
done
```

For monorepos, also check subdirectories -- find all `.env*` files (excluding `node_modules` and `.git`) in `$REPO_ROOT` and copy them to the same relative paths in the worktree:

```bash
find "$REPO_ROOT" -mindepth 2 -name '.env*' -not -path '*/node_modules/*' -not -path '*/.git/*' | while read src; do
  rel="${src#$REPO_ROOT/}"
  mkdir -p "$FIX_WT/$(dirname "$rel")"
  cp "$src" "$FIX_WT/$rel"
done
```

If the project has a `.env.example` or `.env.template` in the repo root but no `.env`, warn the user: "No `.env` file found. The build may fail if environment variables are required."

**Do not log or display the contents of these files** -- they may contain secrets.

Make all fixes in this worktree. Commit them as **new commits on top** of the existing branch -- never amend existing commits. Then do a **regular push** (not force push):

```bash
git -C ../$REPO_NAME-wt-fix-pr<N> push
```

This is safe because the branch already exists on the remote and you are only adding commits. After pushing, remove the worktree:

```bash
git worktree remove ../$REPO_NAME-wt-fix-pr<N>
```

### Phase 9 -- Apply Verdict

Two paths depending on the final confirmed verdict:

#### Path A: Approve

1. **Post a short approval comment** highlighting the best parts of the PR (concise, 2-4 bullet points on what was done well -- good patterns, clean logic, etc.).
2. **Approve the PR** via `gh`.

```bash
gh pr review <PR> --repo <owner/repo> --approve --body "$(cat <<'EOF'
<approval comment body>
EOF
)"
```

#### Path B: Request Changes

1. **Build a review comment** from the review report. Include **all** items (High, Medium, and Low) as a numbered list grouped by priority, with file paths and clear descriptions. Each group should be clearly labeled with its priority heading so the author knows what is blocking vs. nice-to-have.
2. **Submit as a "request changes" review** via `gh`.

```bash
gh pr review <PR> --repo <owner/repo> --request-changes --body "$(cat <<'EOF'
<request changes comment body>
EOF
)"
```

### Phase 10 -- Offer to Merge

This phase only applies when Phase 9 Path A (Approve) was executed. Skip this phase entirely for Path B (Request Changes) or when the user chose "Plan to address issues" in Phase 8.

After the approval is posted, explicitly ask the user:

> "PR approved. Would you like me to squash-merge it and delete the source branch?"

Do not proceed until the user responds. If the user confirms, merge the PR:

```bash
gh pr merge <PR> --repo <owner/repo> --squash --delete-branch
```

If the user declines, do not merge. Proceed to Phase 11 (cleanup).

### Phase 11 -- Cleanup Worktrees

After the review is complete (verdict applied or user chose "Plan to address issues"), remove all worktrees created during the review:

```bash
git worktree remove ../$REPO_NAME-wt-review-pr<N>
```

If the PR head worktree was also created:

```bash
git worktree remove ../$REPO_NAME-wt-review-pr<N>-head
```

If removal fails (e.g., modified files in the worktree), force it:

```bash
git worktree remove --force ../$REPO_NAME-wt-review-pr<N>
```

Also clean up the local `pr-<N>` branch ref if it was created for the head worktree:

```bash
git branch -D pr-<N>
```

---

## Important Principles

- **Only actionable items**: If it doesn't require a change, don't include it.
- **Be specific**: Always reference exact file paths. Never say "in some places" -- say exactly where.
- **Be direct**: State the problem and the fix in one or two sentences. No preamble, no elaboration.
- **Be constructive**: For every problem, suggest a concrete fix.
- **Respect the codebase**: The existing code is the authority. New code should match existing patterns, even if you personally prefer a different approach.
- **No false positives**: Only flag real issues. Do not invent problems. If unsure, leave it out.
- **Prioritize correctly**: Bugs and misleading behavior are High. Pattern deviations are Medium. Nitpicks are Low.
- **Always confirm before acting**: Never approve, merge, or request changes without explicit user confirmation.
