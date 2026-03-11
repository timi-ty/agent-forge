---
name: issue-resolution-report
description: Write and post a technically sound issue resolution report as a GitHub issue comment and/or PR description after fixing a bug or completing a task. Use when the user asks to write a resolution report, document what was fixed, update a PR body with findings, or post a resolution comment on a GitHub issue.
---

# Issue Resolution Report

## Step 1 — Gather proof before writing

Run the appropriate verification step and capture its output before drafting the report. You need:
- The exact command run
- The key output lines that confirm resolution

The form of evidence depends on what was fixed:
- Tests: pass/fail counts and exit code from the test runner
- Build: final build output and exit code
- Runtime behaviour: before/after command output, API response, or log lines
- Correctness: a reproduction command that shows the bug is gone
- Visual changes (UI, layout, rendering): screenshots

Capture enough output to be self-contained — actual terminal lines, not a paraphrase.

**Visual evidence:** When the fix has a visible effect (UI rendering, layout, formatting, icon, colour, preview image), the agent cannot upload screenshots directly. Instead:
1. Identify the specific before/after states that prove the fix.
2. Insert named placeholders in the report at the point where the screenshot belongs.
3. Tell the user exactly what to capture and where to place it.

Placeholder format:
```
![before: <description of what to show>](screenshot-before.png)
![after: <description of what to show>](screenshot-after.png)
```

Example instruction to the user:
> Screenshot needed: open the file manager, navigate to a volume icon. Take one screenshot before applying the fix (icon missing) and one after (icon visible). Replace the placeholders `screenshot-before.png` and `screenshot-after.png` in the PR description.

## Step 2 — Report structure

Every resolution report uses this skeleton, in order:

```
**PR:** <owner>/<repo>#<number>
**Branch:** `<branch-name>`
**Verified:** <one-line proof summary>

---

### Root cause summary
<One paragraph: what was broken and why it was not working against the base branch.>

---

### Change 1 — `path/to/file` *(new file — if applicable)*
**Bug / Purpose:** ...
**Fix:** ...
**Impact radius:** ...

### Change 2 — `path/to/file`
...

---

### Verification
\```
$ <command>
<key output lines>
<relevant terminal output confirming resolution>
\```
```

## Step 3 — Per-change entry

For **every** file that differs from the base branch, write one entry:

- **Bug / Purpose** — what is wrong or missing in the base. For new files, what gap they fill.
- **Fix** — what the code does and why this approach was chosen.
- **Impact radius** — which other code paths are affected. State explicitly whether production code is touched. If test-only, say so.

Use `git diff main..HEAD --stat` to get the definitive file list.

## Writing rules

These are non-negotiable:

1. **No self-reference.** Never write "we", "our", "I", "this PR", "during debugging", or any phrase that describes the work process rather than the code. The report describes the *state of the code vs base*, not the history of changes.

2. **No evolution language.** "removed X", "added X", "rewrote X", "previously" → banned. Instead: "X does Y" (present tense, code state) or "X is absent in base".

3. **Present tense for bugs.** "the function returns bytes" not "the function was returning bytes".

4. **Impact radius must be explicit.** Vague: "no impact". Required: "only called from test setup scripts; no production code touched" or "shared utility used by two test files only; no production callers".

5. **Proof block uses actual output.** Never paraphrase test results. Paste the real terminal lines.

## Posting commands

```bash
# Update PR description
gh pr edit <number> --body "$(cat <<'EOF'
...report text...
EOF
)"

# Post as issue comment (cross-repo: specify --repo)
gh issue comment <number> --repo <owner>/<repo> --body "$(cat <<'EOF'
...report text...
EOF
)"

# Edit an existing comment
gh api --method PATCH repos/<owner>/<repo>/issues/comments/<comment-id> \
  --field body="...updated text..."

# Delete a comment
gh api --method DELETE repos/<owner>/<repo>/issues/comments/<comment-id>
```

To find a comment ID: `gh api repos/<owner>/<repo>/issues/<number>/comments | python3 -c "import sys,json; [print(c['id'], c['body'][:60]) for c in json.load(sys.stdin)]"`

## Self-review checklist

Before posting, scan the full text:

- [ ] No "we", "our", "I", "this PR", or "during debugging" anywhere
- [ ] No "removed/added/rewrote/consolidated/cleaned up X" — rephrase to what X *is*
- [ ] Every changed file has a **Bug/Purpose**, **Fix**, and **Impact radius**
- [ ] Impact radius explicitly states production vs test-only
- [ ] Proof block contains actual output from the real verification step, not a paraphrase
- [ ] Tense is present throughout (bugs described as current code state)
