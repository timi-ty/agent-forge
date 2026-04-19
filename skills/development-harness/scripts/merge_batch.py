#!/usr/bin/env python3
"""Serially merge a dispatched batch's per-unit branches back into HEAD.

Consumes ``state.execution.fleet`` as left behind by ``dispatch_batch.py``.
For each unit in ``fleet.units`` (in list order) the flow is:

  1. **Scope check** -- read the unit's declared ``touches_paths`` from its
     ``WORKTREE_UNIT.json`` and compute ``git diff --name-only
     <merge-base>..<branch>``. Any changed file matching none of the
     declared globs is a scope violation; the unit is rejected before
     any merge attempt with ``conflict = {paths: [...], category:
     "scope_violation"}``. The sub-agent's self-report is never trusted
     for blast radius. Scope failures are always hard rejects regardless
     of ``conflict_strategy``.
  2. **Merge** -- ``git merge --no-ff harness/<batch_id>/<unit_id> -m
     "harness: merge <unit_id>"``.

Outcomes per unit:

  * **Clean merge** -> fleet entry ``status`` flips to ``"merged"``,
    ``conflict`` stays ``null``, ``ended_at`` is stamped.
  * **Conflict** -> ``git merge --abort`` is always run first; then the
    configured ``conflict_strategy`` decides the batch-level behavior:
    - ``"abort_batch"`` (default): record the conflict on the unit's
      fleet entry (``status="failed"``, ``conflict={paths, strategy_applied}``),
      mark every remaining unit ``status="failed"`` with ``conflict=null``
      (they were skipped, not conflicted), and stop.
    - ``"serialize_conflicted"``: record the conflict but leave the unit's
      ``status="running"`` so its worktree and branch stay alive for a
      later batch. Continue merging remaining units.

After every unit has been processed, the caller-supplied
``run_post_merge_validation(root, merged_unit_ids)`` callable is invoked
(default: no-op). On validation failure, ``git reset --hard <pre_merge_ref>``
restores the main branch to its pre-dispatch state and every previously
merged unit is downgraded to ``status="failed"`` with a
``post_merge_validation_failed`` conflict record.

On success, every unit with ``status="merged"`` has its worktree removed
(``git worktree remove --force``) and its branch deleted (``git branch -D``).
``fleet.mode`` ends at ``"idle"``; units with ``status="running"`` (deferred
by ``serialize_conflicted``) keep their worktree and branch.

Uses only Python 3 stdlib. Imports from ``harness_utils``.
"""
import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

from harness_utils import find_harness_root, now_iso, read_json, write_json


HARNESS_DIR = ".harness"

VALID_STRATEGIES = ("abort_batch", "serialize_conflicted")


class MergeError(RuntimeError):
    """Raised when merge_batch encounters a non-recoverable failure."""


def _run_git(args, root, check=True):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _current_head(root):
    return _run_git(["rev-parse", "HEAD"], root).stdout.strip()


def _conflicting_paths(root):
    """Return the files currently marked unmerged, newline-split and trimmed."""
    out = _run_git(
        ["diff", "--name-only", "--diff-filter=U"], root, check=False
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


def _merge_unit(branch, unit_id, root):
    """Attempt ``git merge --no-ff``. Returns ``(clean, conflicting_paths)``."""
    message = f"harness: merge {unit_id}"
    result = _run_git(
        ["merge", "--no-ff", branch, "-m", message], root, check=False
    )
    if result.returncode == 0:
        return True, []
    paths = _conflicting_paths(root)
    _run_git(["merge", "--abort"], root, check=False)
    return False, paths


def _reset_hard(root, ref):
    _run_git(["reset", "--hard", ref], root, check=False)


def _remove_worktree_and_branch(root, worktree_path, branch):
    """Best-effort cleanup of one worktree + its branch. Never raises."""
    abs_worktree = Path(root) / worktree_path
    _run_git(
        ["worktree", "remove", "--force", str(abs_worktree)], root, check=False
    )
    _run_git(["branch", "-D", branch], root, check=False)


def _noop_validate(root, merged_unit_ids):
    """Default validator: always succeeds. Caller wires in a real one."""
    return True, f"no-op validator: skipped {len(merged_unit_ids)} merged unit(s)"


def _is_within_scope(file_path, touches_paths):
    """True if ``file_path`` matches at least one glob in ``touches_paths``.

    fnmatch's ``*`` already matches path separators, so patterns like
    ``src/auth/**`` naturally cover recursive descendants without extra
    translation.
    """
    for pattern in touches_paths or []:
        if fnmatch.fnmatchcase(file_path, pattern):
            return True
    return False


def _scope_violations(root, branch, touches_paths):
    """Return files on ``branch`` that touch outside the declared globs.

    Computes ``git diff --name-only <merge-base>..<branch>`` against
    ``HEAD`` (the integration target) and returns the subset of changed
    files that match none of ``touches_paths``. A unit whose declared
    scope is empty (``touches_paths == []``) violates on any touched file.
    """
    merge_base = _run_git(
        ["merge-base", "HEAD", branch], root, check=False
    ).stdout.strip()
    if not merge_base:
        return []
    diff = _run_git(
        ["diff", "--name-only", f"{merge_base}..{branch}"], root, check=False
    )
    if diff.returncode != 0:
        return []
    changed = [line.strip() for line in diff.stdout.splitlines() if line.strip()]
    return [f for f in changed if not _is_within_scope(f, touches_paths)]


def _read_worktree_touches_paths(root, worktree_path):
    """Read declared ``touches_paths`` from the worktree's WORKTREE_UNIT.json.

    Returns the list as written by dispatch_batch, or ``None`` when the
    sentinel file is missing / unreadable (in which case the scope check
    is skipped -- the file is the source of truth and we refuse to
    fabricate a scope from elsewhere).
    """
    unit_json = Path(root) / worktree_path / HARNESS_DIR / "WORKTREE_UNIT.json"
    if not unit_json.exists():
        return None
    try:
        data = json.loads(unit_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return list(data.get("touches_paths") or [])


def _compute_outcome(merged, conflicted, skipped, aborted):
    if not merged and not conflicted and not skipped:
        return "empty"
    if aborted:
        return "aborted"
    if merged and not conflicted:
        return "ok"
    if merged and conflicted:
        return "partial"
    return "all_conflicted"


def merge_batch(
    state,
    root,
    *,
    conflict_strategy="abort_batch",
    run_post_merge_validation=None,
    now=None,
):
    """Serially fan-in the batch recorded in ``state.execution.fleet``.

    Args:
      state: state.json dict. Mutated in place; the caller persists.
      root: main repo working-tree root.
      conflict_strategy: ``"abort_batch"`` or ``"serialize_conflicted"``.
      run_post_merge_validation: optional callable
        ``(root, merged_unit_ids) -> (ok_bool, evidence_str)``. Defaults to
        a no-op that always returns True.
      now: optional ISO-8601 timestamp for deterministic tests.

    Returns:
      ``{"batch_id", "outcome", "merged", "conflicted", "skipped",
         "validation_evidence"}``. ``outcome`` is one of ``"ok"`` (all clean),
      ``"partial"`` (some merged + some conflicted under serialize_conflicted),
      ``"aborted"`` (abort_batch tripped), ``"validation_failed"`` (post-merge
      validation rejected the merges), ``"all_conflicted"`` (no unit merged),
      or ``"empty"`` (no units in fleet).
    """
    if conflict_strategy not in VALID_STRATEGIES:
        raise MergeError(
            f"unknown conflict_strategy: {conflict_strategy!r} "
            f"(expected one of {VALID_STRATEGIES})"
        )

    execution = state.setdefault("execution", {})
    fleet = execution.setdefault("fleet", {})
    units = list(fleet.get("units") or [])
    batch_id = fleet.get("batch_id")

    if not units:
        fleet["mode"] = "idle"
        return {
            "batch_id": batch_id,
            "outcome": "empty",
            "merged": [],
            "conflicted": [],
            "skipped": [],
            "validation_evidence": None,
        }

    ts = now or now_iso()
    fleet["mode"] = "merging"
    pre_merge_ref = _current_head(root)

    merged = []
    conflicted = []
    skipped = []
    aborted = False

    for unit in units:
        unit_status = unit.get("status")
        if aborted:
            unit["status"] = "failed"
            unit["ended_at"] = ts
            unit["conflict"] = None
            skipped.append(unit["unit_id"])
            continue
        if unit_status in ("merged", "failed"):
            continue

        branch = unit["branch"]
        unit_id = unit["unit_id"]

        # Scope check: the sub-agent's self-report is not trusted for blast
        # radius -- the diff is the source of truth. A unit whose changed
        # files fall outside its declared touches_paths is rejected before
        # we even attempt the merge. Scope failures are always hard
        # rejects; conflict_strategy has no effect here.
        touches_paths = _read_worktree_touches_paths(root, unit["worktree_path"])
        if touches_paths is not None:
            violations = _scope_violations(root, branch, touches_paths)
            if violations:
                unit["status"] = "failed"
                unit["ended_at"] = ts
                unit["conflict"] = {
                    "paths": violations,
                    "category": "scope_violation",
                }
                conflicted.append(unit_id)
                continue

        clean, paths = _merge_unit(branch, unit_id, root)
        if clean:
            unit["status"] = "merged"
            unit["ended_at"] = ts
            unit["conflict"] = None
            merged.append(unit_id)
            continue

        conflicted.append(unit["unit_id"])
        unit["conflict"] = {
            "paths": paths,
            "category": "merge_conflict",
            "strategy_applied": conflict_strategy,
        }
        unit["ended_at"] = ts
        if conflict_strategy == "abort_batch":
            unit["status"] = "failed"
            aborted = True
        else:
            pass

    validator = run_post_merge_validation or _noop_validate
    validation_evidence = None
    if merged:
        ok, evidence = validator(root, list(merged))
        validation_evidence = evidence
        if not ok:
            _reset_hard(root, pre_merge_ref)
            for unit in units:
                if unit.get("status") == "merged":
                    unit["status"] = "failed"
                    unit["conflict"] = {
                        "paths": [],
                        "strategy_applied": "post_merge_validation_failed",
                    }
            fleet["mode"] = "idle"
            fleet["units"] = units
            return {
                "batch_id": batch_id,
                "outcome": "validation_failed",
                "merged": [],
                "conflicted": conflicted,
                "skipped": skipped,
                "validation_evidence": evidence,
            }

    for unit in units:
        if unit.get("status") == "merged":
            _remove_worktree_and_branch(
                root, unit["worktree_path"], unit["branch"]
            )

    fleet["mode"] = "idle"
    fleet["units"] = units
    return {
        "batch_id": batch_id,
        "outcome": _compute_outcome(merged, conflicted, skipped, aborted),
        "merged": merged,
        "conflicted": conflicted,
        "skipped": skipped,
        "validation_evidence": validation_evidence,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Serially merge a dispatched batch's per-unit branches back "
            "into HEAD. Applies conflict_strategy on merge conflicts, runs "
            "post-merge validation (no-op by default), and cleans up every "
            "merged unit's worktree and branch on success."
        )
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=None,
        help="Path to state.json (default: <root>/.harness/state.json).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Harness root (default: find via find_harness_root).",
    )
    parser.add_argument(
        "--conflict-strategy",
        choices=VALID_STRATEGIES,
        default="abort_batch",
        help="How to handle merge conflicts (default: abort_batch).",
    )
    args = parser.parse_args()

    root = args.root or find_harness_root()
    if root is None:
        print("Error: no harness root found.", file=sys.stderr)
        sys.exit(1)

    state_path = args.state or (Path(root) / HARNESS_DIR / "state.json")
    if not state_path.exists():
        print(f"Error: state file not found: {state_path}", file=sys.stderr)
        sys.exit(1)
    state = read_json(state_path)

    try:
        result = merge_batch(
            state,
            root=Path(root),
            conflict_strategy=args.conflict_strategy,
        )
    except MergeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    state["last_updated"] = now_iso()
    write_json(state_path, state)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
