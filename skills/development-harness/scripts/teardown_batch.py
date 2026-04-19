#!/usr/bin/env python3
"""Idempotent teardown of harness batch worktrees and branches.

Removes every worktree under ``.harness/worktrees/<batch_id>/`` and every
local branch matching ``harness/<batch_id>/*``. Callable from ``/clear``,
``/sync``, and error-recovery paths: running it twice in a row is a no-op.

Two modes:

  * ``teardown_batch(root, batch_id="<id>")`` -- scoped cleanup for a
    single batch. Used by error recovery when a specific dispatch went
    sideways.
  * ``teardown_batch(root, batch_id=None)`` -- global cleanup of every
    batch directory on disk and every ``harness/batch_*/*`` branch. Used
    by ``/clear`` to blank slate the harness.

Every git invocation runs with ``check=False`` so missing worktrees,
deleted branches, and other "already gone" states never raise. The
returned summary reports what was actually removed this call.

Uses only Python 3 stdlib. Imports from ``harness_utils``.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from harness_utils import find_harness_root


HARNESS_DIR = ".harness"
WORKTREES_DIR = "worktrees"
BRANCH_PREFIX = "harness/"


def _run_git(args, root, check=False):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _worktrees_root(root):
    return Path(root) / HARNESS_DIR / WORKTREES_DIR


def _list_batch_dirs(root, batch_id=None):
    """Return the batch directories to tear down, sorted for stable output."""
    base = _worktrees_root(root)
    if not base.is_dir():
        return []
    if batch_id is not None:
        target = base / batch_id
        return [target] if target.is_dir() else []
    return sorted(p for p in base.iterdir() if p.is_dir())


def _list_unit_worktrees(batch_dir):
    """Return the per-unit worktree directories inside a batch dir."""
    if not batch_dir.is_dir():
        return []
    return sorted(p for p in batch_dir.iterdir() if p.is_dir())


def _list_harness_branches(root, batch_id=None):
    """Return every local branch matching ``harness/<batch_id>/*``.

    When ``batch_id`` is None, matches every ``harness/batch_*/*`` branch.
    """
    result = _run_git(
        ["branch", "--list", "--format=%(refname:short)"], root, check=False
    )
    if result.returncode != 0:
        return []
    branches = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if batch_id is not None:
        prefix = f"{BRANCH_PREFIX}{batch_id}/"
        return [b for b in branches if b.startswith(prefix)]
    return [b for b in branches if b.startswith(BRANCH_PREFIX)]


def _remove_worktree(root, worktree_path):
    """Best-effort ``git worktree remove --force``. Returns success bool."""
    result = _run_git(
        ["worktree", "remove", "--force", str(worktree_path)], root, check=False
    )
    return result.returncode == 0


def _delete_branch(root, branch):
    """Best-effort ``git branch -D``. Returns success bool."""
    result = _run_git(["branch", "-D", branch], root, check=False)
    return result.returncode == 0


def _cleanup_empty_dir(path):
    """Remove ``path`` if it exists and is empty (or contains only empty dirs)."""
    try:
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass


def teardown_batch(root, batch_id=None):
    """Remove worktrees and branches for one batch -- or all batches when
    ``batch_id`` is None.

    Returns:
      ``{"removed_worktrees": [...], "deleted_branches": [...], "batch_ids":
      [...]}`` listing exactly what this invocation removed.
    """
    removed_worktrees = []
    deleted_branches = []
    batch_ids_touched = []

    for batch_dir in _list_batch_dirs(root, batch_id=batch_id):
        this_batch_id = batch_dir.name
        for unit_dir in _list_unit_worktrees(batch_dir):
            if _remove_worktree(root, unit_dir):
                removed_worktrees.append(str(unit_dir.relative_to(root)))
            if unit_dir.exists():
                # git's worktree remove sometimes leaves the directory when
                # the worktree was already orphaned; clean up explicitly.
                shutil.rmtree(unit_dir, ignore_errors=True)
        _cleanup_empty_dir(batch_dir)
        batch_ids_touched.append(this_batch_id)

    # Now branches. `git worktree remove` will have pruned most of these
    # for successfully-removed worktrees, but stale entries can remain
    # (branches whose worktrees were already gone, or whose worktrees
    # were orphaned on disk).
    for branch in _list_harness_branches(root, batch_id=batch_id):
        if _delete_branch(root, branch):
            deleted_branches.append(branch)
            # Parse the batch_id out so it shows up in the summary even
            # when the on-disk batch dir was already missing.
            rest = branch[len(BRANCH_PREFIX):]
            maybe_batch = rest.split("/", 1)[0]
            if maybe_batch and maybe_batch not in batch_ids_touched:
                batch_ids_touched.append(maybe_batch)

    _cleanup_empty_dir(_worktrees_root(root))
    # Let git re-sync its worktree metadata in case we force-removed
    # something it didn't know was gone.
    _run_git(["worktree", "prune"], root, check=False)

    return {
        "removed_worktrees": removed_worktrees,
        "deleted_branches": deleted_branches,
        "batch_ids": batch_ids_touched,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Idempotent teardown of harness batch worktrees and branches. "
            "Default: every batch. Use --batch-id to scope to one batch."
        )
    )
    parser.add_argument(
        "--batch-id",
        default=None,
        help="Limit teardown to a single batch (default: tear down all batches).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Harness root (default: find via find_harness_root).",
    )
    args = parser.parse_args()

    root = args.root or find_harness_root()
    if root is None:
        print("Error: no harness root found.", file=sys.stderr)
        sys.exit(1)

    result = teardown_batch(Path(root), batch_id=args.batch_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
