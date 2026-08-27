---
name: pr-evidence-screenshots
description: Capture a before/after (problem/solution) screenshot pair for a UI fix and embed it inline in a GitHub PR or issue on a PRIVATE repo. Use when asked to "add screenshots to the PR", "show before and after", "prove the fix visually", "add evidence to the issue", or when a UI fix needs visual proof a reviewer can check without running anything.
---

# PR Evidence Screenshots

Produce a pair of images where **the only difference is the code**, then get them
rendering inline on a private GitHub repo.

Two things make this fail, and both are silent:

- A pair captured on different viewports, different data or different waits is
  not evidence — it is two unrelated pictures.
- On a **private** repo most image-hosting routes 404 for a human reviewer while
  passing a `curl` check. You will believe it worked.

## Phase 1 — Two builds, one script

Build **both sides as real production builds**. A dev-server screenshot can
differ from what ships. One detached worktree at the base branch is the "before"
for every fix at once; the fix worktree is the "after".

```bash
REPO=/path/to/repo
WORKTREE_ROOT=${WORKTREE_ROOT:-$HOME/worktrees}
BASE=origin/main                    # whatever this PR targets

git -C $REPO worktree add $WORKTREE_ROOT/<slug>-before --detach $BASE
cd $WORKTREE_ROOT/<slug>-before
cp $REPO/.env.local .env.local      # gitignored, absent in a fresh worktree
pnpm install                        # see gotcha 1 — do NOT symlink node_modules
pnpm build && pnpm start -p 3213
# fix worktree on another port
cd $WORKTREE_ROOT/<slug> && pnpm build && pnpm start -p 3212
```

The build commands above are a pnpm/Next example — substitute your own, but keep
both sides on production builds and on fixed ports.

Always confirm which worktree is actually serving each port before you trust a
frame — a stale server from another session is the classic wrong-code screenshot.
`ss` and `/proc` are Linux/WSL; on macOS use `lsof -nP -iTCP:$p -sTCP:LISTEN`:

```bash
for p in 3212 3213; do
  PID=$(ss -lptn "sport = :$p" | grep -oP 'pid=\K[0-9]+' | head -1)
  echo "$p -> $(readlink -f /proc/$PID/cwd)"
done
```

Then drive **one script** against both, taking `baseURL`, `outDir` and a
`problem` / `solution` label. `scripts/capture-pair.mjs` in this skill directory
is a working template — copy it, edit the flow, keep the structure. It reads
the sign-in credentials from `EVIDENCE_EMAIL` and `EVIDENCE_PASSWORD`, so
nothing secret lives in the file you commit.

Run it with `unset DISPLAY` — a dead `$DISPLAY` (common under WSL) makes
headless screenshots hang rather than fail.

## Phase 2 — Make the image checkable

A screenshot alone is unfalsifiable. Print the same fact from the DOM so the run
log corroborates the pixels, and paste both into the PR:

```js
// the state under test, read straight out of the table/row/panel
const readBack = await page.evaluate(() => …);
console.log(`  row after reload reads: ${JSON.stringify(readBack)}`);
// and any on-screen error text
const alerts = await page.evaluate(() =>
  Array.from(document.querySelectorAll('[role="alert"], p.text-red-600'))
    .map((el) => el.textContent?.trim()).filter(Boolean));
```

**Never** assert presence with `document.body.textContent.includes(x)** — see
gotcha 4.

## Phase 3 — Publish so a human can see them

On a private repo, push the PNGs to a **slash-free orphan branch in the same
repo** and link via `/raw/`:

```bash
cd <outDir>
rm -rf .git && git init -q && git checkout -q -b evidence-pr-<N>
git add *.png
git commit -q -m "evidence: PR <N> before/after screenshots (delete after review)"
git remote add origin git@github.com:OWNER/REPO.git
git push -q origin evidence-pr-<N>
```

Reference them as:

```markdown
![before](https://github.com/OWNER/REPO/raw/evidence-pr-<N>/problem-3.png)
```

- `https://github.com/OWNER/REPO/raw/BRANCH/f.png` — authenticated by the
  viewer's **github.com session cookie**, renders for any signed-in member ✅
- `https://raw.githubusercontent.com/...` — needs a **token** a browser never
  sends. 200s under `curl -H "Authorization: …"`, 404s for a human ❌
- `user-attachments` (drag-and-drop) needs a browser session a PAT cannot reach ❌

Present the pair as a two-column table so the frames sit side by side, and say
in the comment that the branch is evidence-only and should be deleted.

## Phase 4 — Verify what GitHub rendered

Check the stored HTML, not what you wrote. A `camo.githubusercontent.com` src
means GitHub treated it as external and it **will** break on a private asset:

```bash
gh api repos/OWNER/REPO/issues/comments/<id> \
  -H "Accept: application/vnd.github.html+json" --jq '.body_html' |
  grep -oE '<img src="[^"]*"'
```

Your URLs intact = good.

## Phase 5 — Clean up

Restore any record the capture mutated (the "after" run writes real data), stop
both servers, remove the before-worktree, and tell the reviewer the evidence
branch is theirs to delete.

## Gotchas that cost real time

1. **Turbopack rejects a symlinked `node_modules`** — `FATAL: An unexpected
   Turbopack error occurred … Symlink node_modules is invalid, it points out of
   the filesystem root`. Symlinking from a sibling worktree is fine for `vitest`
   but fatal for `next build`. Run a real `pnpm install` in the before-worktree.
2. **A capture script in the scratchpad cannot resolve `@playwright/test`.** Put
   it inside a worktree (the disposable before-worktree is ideal — it is deleted
   with everything else) and run it from there.
3. **A local git hook may block `git -c user.email=…`.** Author-guard hooks are
   common in agent setups. The global identity is already correct, so plain
   `git commit` in the fresh evidence repo does the right thing. Do not pass `-c`.
4. **`document.body.textContent.includes(value)` is a false positive** — the
   search box you just typed into contributes to it, so a lost value reads as
   present. Read the specific cells (`querySelectorAll('table tbody tr')[0]
   .querySelectorAll('td')`) instead.
5. **Fixed `waitForTimeout` guesses flake on a cold production start.** Wait on
   the thing itself (`locator(...).waitFor({state:'visible'})`) for anything the
   first render has to fetch.
6. **Repeated logins can trip auth-provider rate limits.** Sign-in starts failing
   for every user at once, which reads as a broken build. Space the runs out; it
   usually clears in minutes.
