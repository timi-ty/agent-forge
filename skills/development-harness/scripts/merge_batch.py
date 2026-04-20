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

The whole flow is wrapped in an ``.harness/.lock`` ``O_EXCL`` file mutex
so two concurrent invokers cannot interleave merges. A second caller
blocks until the first releases; a lock file older than
``lock_stale_after`` seconds (default 600) is treated as abandoned and
taken over.

Uses only Python 3 stdlib. Imports from ``harness_utils``.
"""
import argparse
import fnmatch
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from harness_utils import find_harness_root, now_iso, read_json, write_json


HARNESS_DIR = ".harness"
LOCK_FILENAME = ".lock"
LOGS_DIR = "logs"

VALID_STRATEGIES = ("abort_batch", "serialize_conflicted")

DEFAULT_LOCK_TIMEOUT = 300.0        # wait up to 5 min for the lock
DEFAULT_LOCK_STALE_AFTER = 600.0    # a lock mtime older than 10 min is stale
DEFAULT_LOCK_POLL_INTERVAL = 0.1


class MergeError(RuntimeError):
    """Raised when merge_batch encounters a non-recoverable failure."""


class _MergeLock:
    """File-based mutex backed by ``os.O_EXCL`` on ``<root>/.harness/.lock``.

    The first acquirer wins immediately; subsequent acquirers **block**,
    polling on ``poll_interval`` until either the file is removed by the
    holder (normal release) or the file's mtime exceeds
    ``stale_after_seconds`` (take-over after a crashed holder). If
    ``timeout`` elapses without acquisition, ``MergeError`` is raised.

    The lock file's body is ``"<pid> <iso_ts>\\n"`` for human inspection
    and for stale-detection debugging.
    """

    def __init__(
        self,
        root,
        *,
        timeout=DEFAULT_LOCK_TIMEOUT,
        stale_after_seconds=DEFAULT_LOCK_STALE_AFTER,
        poll_interval=DEFAULT_LOCK_POLL_INTERVAL,
    ):
        self.path = Path(root) / HARNESS_DIR / LOCK_FILENAME
        self.timeout = float(timeout)
        self.stale_after_seconds = float(stale_after_seconds)
        self.poll_interval = float(poll_interval)
        self._fd = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        body = f"{os.getpid()} {now_iso()}\n".encode("utf-8")
        while True:
            try:
                self._fd = os.open(
                    str(self.path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.write(self._fd, body)
                return
            except FileExistsError:
                if self._is_stale():
                    try:
                        os.unlink(self.path)
                    except OSError:
                        pass
                    continue
                if time.monotonic() - start >= self.timeout:
                    raise MergeError(
                        f"timed out waiting for merge lock at {self.path} "
                        f"(timeout={self.timeout}s, stale_after={self.stale_after_seconds}s)"
                    )
                time.sleep(self.poll_interval)

    def release(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def _is_stale(self):
        try:
            age = time.time() - self.path.stat().st_mtime
        except OSError:
            return False
        return age >= self.stale_after_seconds

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


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


def _prune_empty_dir(path):
    """Remove ``path`` if it exists and contains no entries. Never raises."""
    try:
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass


def _write_batch_log(root, batch_id, filename, content):
    """Best-effort append-or-write of one log artifact under
    ``.harness/logs/<batch_id>/``. Log writes never block the merge --
    a missing or unwritable log dir is a reportability miss, not a
    correctness failure. Returns ``True`` on success, ``False`` on any
    ``OSError``.

    ``content`` accepts a dict/list (serialized as JSON) or a string
    (written verbatim).
    """
    if not batch_id:
        return False
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


def _render_merge_log(batch_id, result):
    """Render a human-readable merge summary for .harness/logs/<batch>/merge.log.

    Keep the shape grep-friendly: one header line, then one bullet per
    unit category (merged/conflicted/skipped). Consumers (the /harness-state
    renderer, humans debugging a failed batch) parse this as text.
    """
    lines = [
        f"batch_id: {batch_id}",
        f"outcome: {result['outcome']}",
        f"merged ({len(result['merged'])}):",
    ]
    for uid in result["merged"]:
        lines.append(f"  - {uid}")
    lines.append(f"conflicted ({len(result['conflicted'])}):")
    for uid in result["conflicted"]:
        lines.append(f"  - {uid}")
    lines.append(f"skipped ({len(result['skipped'])}):")
    for uid in result["skipped"]:
        lines.append(f"  - {uid}")
    return "\n".join(lines) + "\n"


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
    lock_timeout=DEFAULT_LOCK_TIMEOUT,
    lock_stale_after=DEFAULT_LOCK_STALE_AFTER,
    lock_poll_interval=DEFAULT_LOCK_POLL_INTERVAL,
):
    """Serially fan-in the batch recorded in ``state.execution.fleet``.

    Wraps the full flow in a ``.harness/.lock`` ``O_EXCL`` mutex so two
    concurrent invokers cannot interleave merges. Blocks on acquisition
    (polling every ``lock_poll_interval`` seconds up to ``lock_timeout``)
    or takes over a lock whose file mtime exceeds ``lock_stale_after``.

    Args:
      state: state.json dict. Mutated in place; the caller persists.
      root: main repo working-tree root.
      conflict_strategy: ``"abort_batch"`` or ``"serialize_conflicted"``.
      run_post_merge_validation: optional callable
        ``(root, merged_unit_ids) -> (ok_bool, evidence_str)``. Defaults to
        a no-op that always returns True.
      now: optional ISO-8601 timestamp for deterministic tests.
      lock_timeout: seconds to wait for ``.harness/.lock`` before raising
        ``MergeError``. Default: 300.
      lock_stale_after: seconds after which an existing lock file is
        treated as abandoned and forcibly taken over. Default: 600.
      lock_poll_interval: seconds between acquisition retries. Default: 0.1.

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

    with _MergeLock(
        root,
        timeout=lock_timeout,
        stale_after_seconds=lock_stale_after,
        poll_interval=lock_poll_interval,
    ):
        return _merge_batch_locked(
            state,
            root,
            conflict_strategy=conflict_strategy,
            run_post_merge_validation=run_post_merge_validation,
            now=now,
        )


def _merge_batch_locked(
    state,
    root,
    *,
    conflict_strategy,
    run_post_merge_validation,
    now,
):
    """Internal core: runs inside the held merge lock. See ``merge_batch``."""

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
        # Observability: persist the validator's message regardless of
        # outcome. Runs before the rollback branch below so a failed
        # validation still leaves a .harness/logs/<batch>/validation.log
        # to inspect. Best-effort; never blocks merge on a log error.
        try:
            _write_batch_log(
                root, batch_id, "validation.log",
                f"validator_ok: {ok}\n{evidence}\n",
            )
        except Exception:
            pass
        if not ok:
            _reset_hard(root, pre_merge_ref)
            for unit in units:
                if unit.get("status") == "merged":
                    unit["status"] = "failed"
                    unit["conflict"] = {
                        "paths": [],
                        "category": "post_merge_validation_failed",
                        "strategy_applied": "post_merge_validation_failed",
                    }
            fleet["mode"] = "idle"
            fleet["units"] = units
            result = {
                "batch_id": batch_id,
                "outcome": "validation_failed",
                "merged": [],
                "conflicted": conflicted,
                "skipped": skipped,
                "validation_evidence": evidence,
            }
            try:
                _write_batch_log(
                    root, batch_id, "merge.log",
                    _render_merge_log(batch_id, result),
                )
            except Exception:
                pass
            return result

    for unit in units:
        if unit.get("status") == "merged":
            _remove_worktree_and_branch(
                root, unit["worktree_path"], unit["branch"]
            )

    # Prune now-empty `.harness/worktrees/<batch_id>/` and the shared
    # worktrees root when they have nothing left. A deferred unit
    # (serialize_conflicted) or a scope-violator keeps its worktree,
    # so these dirs only disappear when the whole batch is resolved.
    batch_id_for_cleanup = fleet.get("batch_id")
    if batch_id_for_cleanup:
        _prune_empty_dir(Path(root) / HARNESS_DIR / "worktrees" / batch_id_for_cleanup)
    _prune_empty_dir(Path(root) / HARNESS_DIR / "worktrees")

    fleet["mode"] = "idle"
    fleet["units"] = units
    result = {
        "batch_id": batch_id,
        "outcome": _compute_outcome(merged, conflicted, skipped, aborted),
        "merged": merged,
        "conflicted": conflicted,
        "skipped": skipped,
        "validation_evidence": validation_evidence,
    }
    # Observability: write a grep-friendly merge summary for
    # /harness-state and post-hoc inspection. Best-effort; never
    # blocks the merge on a log error.
    try:
        _write_batch_log(
            root, batch_id, "merge.log", _render_merge_log(batch_id, result),
        )
    except Exception:
        pass
    return result


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
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=DEFAULT_LOCK_TIMEOUT,
        help=(
            "Seconds to wait for .harness/.lock before aborting. Default: "
            f"{DEFAULT_LOCK_TIMEOUT}."
        ),
    )
    parser.add_argument(
        "--lock-stale-after",
        type=float,
        default=DEFAULT_LOCK_STALE_AFTER,
        help=(
            "Seconds after which an existing lock file is treated as "
            f"abandoned and forcibly taken over. Default: {DEFAULT_LOCK_STALE_AFTER}."
        ),
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
            lock_timeout=args.lock_timeout,
            lock_stale_after=args.lock_stale_after,
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
