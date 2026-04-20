#!/usr/bin/env python3
"""Dispatch a parallel batch: create per-unit git worktrees and seed fleet state.

Consumes the JSON output of ``compute_parallel_batch.py`` (``{batch_id, batch,
excluded}``). Per unit in the batch:

  * ``git worktree add -b harness/<batch_id>/<unit_id>
    .harness/worktrees/<batch_id>/<unit_id> HEAD``
  * Seed ``<worktree>/.harness/WORKTREE_UNIT.json`` with ``batch_id``,
    ``unit_id``, ``phase_id``, and the unit's declared ``touches_paths``.
  * Append a ``status: "running"`` entry to ``state.execution.fleet.units``.

Atomic on failure: if any per-unit step fails, every worktree and branch
created by this dispatch is torn down before ``DispatchError`` propagates.
The caller ends up in the same on-disk / in-state condition it started in.

Uses only Python 3 stdlib. Imports from ``harness_utils``.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from harness_utils import find_harness_root, now_iso, read_json, write_json


HARNESS_DIR = ".harness"
WORKTREES_DIR = "worktrees"
LOGS_DIR = "logs"


class DispatchError(RuntimeError):
    """Raised when dispatch fails after rollback of partial state."""


def _write_batch_log(root, batch_id, filename, content):
    """Best-effort write of one log artifact under ``.harness/logs/<batch_id>/``.

    Log writes must never block the orchestrator -- a missing or
    unwritable log dir is a reportability miss, not a correctness
    failure. Wraps every step in ``try/except OSError``; on failure it
    returns ``False`` without raising. The caller may log but must not
    propagate.

    ``content`` accepts a dict/list (serialized as JSON) or a string
    (written verbatim). Parameter name matches ``merge_batch._write_batch_log``.
    """
    try:
        log_dir = Path(root) / HARNESS_DIR / LOGS_DIR / batch_id
        log_dir.mkdir(parents=True, exist_ok=True)
        target = log_dir / filename
        if isinstance(content, (dict, list)):
            target.write_text(
                json.dumps(content, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        else:
            target.write_text(str(content), encoding="utf-8")
        return True
    except OSError:
        return False


def _worktree_relpath(batch_id, unit_id):
    """Repo-relative POSIX path for a unit's worktree directory."""
    return f"{HARNESS_DIR}/{WORKTREES_DIR}/{batch_id}/{unit_id}"


def _branch_name(batch_id, unit_id):
    """Git branch name for a unit's worktree."""
    return f"harness/{batch_id}/{unit_id}"


def _run_git(args, root, check=True):
    """Run ``git -C <root> <args>``. Returns the CompletedProcess."""
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _create_worktree(root, batch_id, unit_id):
    """Create the worktree + branch for one unit. Returns ``(abs_path, branch)``."""
    abs_path = Path(root) / _worktree_relpath(batch_id, unit_id)
    branch = _branch_name(batch_id, unit_id)
    _run_git(
        ["worktree", "add", "-b", branch, str(abs_path), "HEAD"],
        root=root,
        check=True,
    )
    return abs_path, branch


def _seed_worktree_unit_json(worktree_path, batch_id, unit_id, phase_id, touches_paths):
    """Write ``<worktree>/.harness/WORKTREE_UNIT.json`` with unit metadata."""
    target_dir = Path(worktree_path) / HARNESS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch_id": batch_id,
        "unit_id": unit_id,
        "phase_id": phase_id,
        "touches_paths": list(touches_paths or []),
    }
    write_json(target_dir / "WORKTREE_UNIT.json", payload)


def _remove_worktree(root, worktree_path, branch):
    """Best-effort cleanup of one worktree and its branch. Never raises."""
    _run_git(
        ["worktree", "remove", "--force", str(worktree_path)],
        root=root,
        check=False,
    )
    _run_git(["branch", "-D", branch], root=root, check=False)


def _rollback(root, created):
    """Tear down every (worktree, branch) pair created by this dispatch."""
    for worktree_path, branch in created:
        _remove_worktree(root, worktree_path, branch)


def dispatch_batch(batch_result, root, state=None, now=None):
    """Create worktrees for every unit in ``batch_result['batch']``.

    Args:
      batch_result: ``{batch_id, batch, excluded}`` dict as produced by
        ``compute_parallel_batch.compute_batch``. Only ``batch_id`` and
        ``batch`` are read; ``excluded`` is ignored.
      root: Harness root (the repo's working-tree root).
      state: Optional ``state.json`` dict. When provided, its
        ``execution.fleet`` is replaced with the new fleet block in place.
        The caller is responsible for persisting the mutated state.
      now: Optional ISO-8601 timestamp string for deterministic tests.

    Returns:
      ``{"batch_id", "fleet": {"mode", "batch_id", "units"}}`` where every
      unit entry matches the v2 ``state.execution.fleet.units[*]`` shape
      with ``status="running"``, ``ended_at=None``, ``agent_summary_path=None``,
      ``conflict=None``.

    Raises:
      DispatchError: If any per-unit step fails. Before raising, every
        worktree and branch created earlier in the same call is removed
        so the repo is back to its pre-dispatch state.
    """
    batch_id = batch_result["batch_id"]
    batch = batch_result.get("batch") or []
    ts = now or now_iso()

    created = []
    fleet_units = []

    try:
        for unit in batch:
            unit_id = unit["id"]
            phase_id = unit.get("phase_id")
            worktree_path, branch = _create_worktree(root, batch_id, unit_id)
            created.append((worktree_path, branch))
            _seed_worktree_unit_json(
                worktree_path,
                batch_id,
                unit_id,
                phase_id,
                unit.get("touches_paths"),
            )
            fleet_units.append(
                {
                    "unit_id": unit_id,
                    "phase_id": phase_id,
                    "worktree_path": _worktree_relpath(batch_id, unit_id),
                    "branch": branch,
                    "status": "running",
                    "started_at": ts,
                    "ended_at": None,
                    "agent_summary_path": None,
                    "conflict": None,
                }
            )
    except (subprocess.CalledProcessError, OSError, KeyError) as exc:
        _rollback(root, created)
        raise DispatchError(f"dispatch failed: {exc}") from exc

    fleet = {"mode": "dispatched", "batch_id": batch_id, "units": fleet_units}
    if state is not None:
        state.setdefault("execution", {})["fleet"] = fleet

    # Observability: snapshot the batch plan + dispatched fleet under
    # .harness/logs/<batch_id>/batch.json for /harness-state and
    # post-hoc inspection. Best-effort; a log write failure never
    # aborts a successful dispatch -- the outer try/except catches
    # anything the helper misses (it shouldn't, but the call site
    # owns the non-blocking guarantee).
    try:
        _write_batch_log(
            root,
            batch_id,
            "batch.json",
            {
                "batch_id": batch_id,
                "dispatched_at": ts,
                "batch_plan": batch_result,
                "fleet": fleet,
            },
        )
    except Exception:
        pass

    return {"batch_id": batch_id, "fleet": fleet}


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Dispatch a parallel batch: create git worktrees for each unit, "
            "seed WORKTREE_UNIT.json, and write state.execution.fleet. Atomic "
            "teardown on failure."
        )
    )
    parser.add_argument(
        "--batch",
        type=Path,
        required=True,
        help="Path to batch JSON (output of compute_parallel_batch.py).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Harness root (default: find via find_harness_root).",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=None,
        help="Path to state.json (default: <root>/.harness/state.json).",
    )
    args = parser.parse_args()

    root = args.root or find_harness_root()
    if root is None:
        print("Error: no harness root found.", file=sys.stderr)
        sys.exit(1)

    if not args.batch.exists():
        print(f"Error: batch file not found: {args.batch}", file=sys.stderr)
        sys.exit(1)
    batch_result = read_json(args.batch)

    state_path = args.state or (Path(root) / HARNESS_DIR / "state.json")
    state = read_json(state_path) if state_path.exists() else {}

    try:
        result = dispatch_batch(batch_result, root=Path(root), state=state)
    except DispatchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    if state_path.exists():
        state["last_updated"] = now_iso()
        write_json(state_path, state)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
