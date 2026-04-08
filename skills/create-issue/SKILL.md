---
name: create-issue
description: Analyze the current conversation to identify a problem worth tracking, ask the user filtering questions, then create a well-structured GitHub issue with appropriate labels, assignee, and project settings. Use when the user says "create an issue", "open an issue", "file an issue", "create github issue", "log this as an issue", or "track this as an issue".
---

# Create Issue

Analyze the current agent conversation to extract a problem or improvement worth tracking, refine it with the user, and create a well-structured GitHub issue.

**Dependencies:** `gh` CLI

---

## Workflow

```
Progress:
- [ ] Phase 1: Analyze the conversation
- [ ] Phase 2: Determine the target repository
- [ ] Phase 3: Ask filtering questions
- [ ] Phase 4: Draft the issue
- [ ] Phase 5: Show draft and confirm
- [ ] Phase 6: Create the issue
```

### Phase 1 -- Analyze the conversation

Review the full conversation history to extract:

1. **What happened** -- the problem, bug, failure, or improvement identified
2. **Root cause** (if known) -- what is actually broken or missing
3. **Reproduction steps** (if applicable) -- how to trigger the issue
4. **Affected components** -- which files, modules, or systems are involved
5. **Severity/impact** -- how bad is it, who is affected
6. **Proposed solution** (if discussed) -- what fix was identified or attempted

Synthesize this into a draft issue structure. Do NOT create the issue yet.

### Phase 2 -- Determine the target repository

1. Check if the current working directory is a git repo. If so, extract `owner/repo` from the git remote:

```bash
gh repo view --json nameWithOwner --jq '.nameWithOwner'
```

2. Ask the user: "Should this issue go to **owner/repo**, or a different repository?"
3. If a different repo, ask for the target `owner/repo` identifier.

### Phase 3 -- Filtering questions

Ask the user a focused set of questions to refine the issue. Present them **all at once** so the user can answer in a single response:

1. **Title** -- propose a concise title based on the conversation. Ask: "Proposed title: `<title>`. Want to adjust it?"
2. **Scope** -- "Should the issue cover [full scope from conversation] or just [subset]?"
3. **Labels** -- fetch available labels from the target repo and propose labels based on the issue type:

```bash
gh label list --repo <owner/repo> --limit 100 --json name,description --jq '.[] | "\(.name): \(.description)"'
```

Ask: "Proposed labels: `<label1>`, `<label2>`. Add/remove any?"

4. **Assignee** -- "Who should this be assigned to? (GitHub username, or leave blank)"
5. **Milestone** -- fetch milestones and offer them if any exist:

```bash
gh api repos/<owner>/<repo>/milestones --jq '.[] | "\(.number): \(.title)"'
```

If milestones exist, ask which one. Otherwise skip.

6. **Priority** -- if the repo uses priority labels (e.g., `priority:high`, `P0`), ask. Otherwise skip.
7. **Additional context** -- "Anything to add that wasn't discussed in our conversation?"

### Phase 4 -- Draft the issue

Write the full issue body using this structure:

```markdown
## Problem

<Clear description of what is wrong or what is needed. Present tense.>

## Context

<How this was discovered. What was being done when the problem surfaced.>

## Reproduction

<Steps to reproduce, if applicable. Skip this section entirely if not a bug.>

## Affected components

- `path/to/file1`
- `path/to/file2`

## Proposed solution

<What fix was discussed, if any. Skip this section entirely if none identified.>
```

#### Linking rules (NON-NEGOTIABLE)

These rules apply to the issue title, body, and all comments:

- **NEVER** use `#123` shorthand anywhere. GitHub auto-links `#N` to the current repo, which produces wrong or broken links in cross-repo contexts.
- **NEVER** use `owner/repo#123` shorthand. This is also unreliable in GitHub-rendered markdown.
- **ALWAYS** use full URLs for all cross-references:
  - Issues: `https://github.com/owner/repo/issues/123`
  - Pull requests: `https://github.com/owner/repo/pull/456`
  - Commits: `https://github.com/owner/repo/commit/abc1234`
  - Discussions: `https://github.com/owner/repo/discussions/789`

### Phase 5 -- Show draft and confirm

Display the complete issue to the user:
- Title
- Full body
- Labels
- Assignee (if any)
- Milestone (if any)
- Target repository

Ask for explicit approval before creating. Wait for the user to say "go ahead" or provide edits. Do NOT create the issue without explicit confirmation.

### Phase 6 -- Create the issue

```bash
gh issue create --repo <owner/repo> \
  --title "<title>" \
  --label "<label1>,<label2>" \
  --assignee "<username>" \
  --milestone "<milestone>" \
  --body "$(cat <<'EOF'
<issue body>
EOF
)"
```

Omit `--assignee` if no assignee was specified. Omit `--milestone` if no milestone was selected. Omit `--label` if no labels were chosen.

After creation, display the issue URL to the user.

---

## Important Principles

- **Never create an issue without explicit user confirmation.** Always show the full draft first.
- **No `#` shorthand.** Full URLs only. This is non-negotiable.
- **Present tense.** Describe the problem as it exists now, not as a narrative of what happened.
- **Be concise.** The issue should be clear and actionable. Do not pad with unnecessary context.
- **Respect the user's scope decisions.** If they say to narrow the issue, narrow it. Do not include material the user excluded.
