#!/usr/bin/env python3
"""Session-scoped safety rails for the development harness invoke loop.

Tracks the count of ``scope_violation`` and ``ambiguity`` failures in an
invoke session. After two such failures, writes
``.harness/.parallel-disabled`` as a kill switch; the invoke flow reads
this file at the start of each turn and forces the in-tree fast path
regardless of ``config.execution_mode.parallelism.enabled``. The kill
switch is cleared by the stop hook when ``.invoke-active`` is cleared
(both files are session-scoped).

Files on disk under ``.harness/``:

  * ``.parallel-failures.jsonl`` -- one JSON line per recorded failure
    (``{category, timestamp, unit_id}``). Only ``scope_violation`` and
    ``ambiguity`` entries count toward the kill-switch threshold.
  * ``.parallel-disabled`` -- presence = kill switch active. Body is a
    small JSON blob with ``reason`` and ``count`` for human inspection.

Uses only Python 3 stdlib. Imports from ``harness_utils``.
"""
import argparse
import json
import sys
from pathlib import Path

from harness_utils import find_harness_root, now_iso


HARNESS_DIR = ".harness"
FAILURES_FILE = ".parallel-failures.jsonl"
KILL_SWITCH_FILE = ".parallel-disabled"

COUNTED_CATEGORIES = ("scope_violation", "ambiguity")
KILL_SWITCH_THRESHOLD = 2


def _failures_path(root):
    return Path(root) / HARNESS_DIR / FAILURES_FILE


def _kill_switch_path(root):
    return Path(root) / HARNESS_DIR / KILL_SWITCH_FILE


def _count_session_failures(path):
    """Count entries in the failure log that count toward the threshold."""
    if not path.is_file():
        return 0
    count = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("category") in COUNTED_CATEGORIES:
                    count += 1
    except OSError:
        return 0
    return count


def record_failure(root, category, unit_id=None, now=None):
    """Append a failure entry; maybe write the kill switch.

    Returns ``True`` when this call flipped the kill switch from absent
    to present, ``False`` otherwise. Failures in categories other than
    ``scope_violation`` / ``ambiguity`` are still logged (for
    observability) but do not count toward the threshold.
    """
    path = _failures_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "category": category,
        "timestamp": now or now_iso(),
        "unit_id": unit_id,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if category not in COUNTED_CATEGORIES:
        return False

    count = _count_session_failures(path)
    if count < KILL_SWITCH_THRESHOLD:
        return False

    kill_switch = _kill_switch_path(root)
    if kill_switch.exists():
        return False  # already tripped earlier in this session

    kill_switch.write_text(
        json.dumps(
            {
                "reason": f"{KILL_SWITCH_THRESHOLD}+ scope_violation/ambiguity failures in session",
                "count": count,
                "triggered_at": now or now_iso(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return True


def is_parallel_disabled(root):
    """Return ``True`` if the kill switch is active for this session."""
    return _kill_switch_path(root).exists()


def clear_safety_rails(root):
    """Remove both the kill switch and the failure log.

    Called by the stop hook when ``.invoke-active`` is cleared, so the
    next session starts with a clean safety-rail state. Missing files
    are fine -- this is idempotent.
    """
    for path in (_kill_switch_path(root), _failures_path(root)):
        try:
            path.unlink()
        except (OSError, FileNotFoundError):
            pass


def _cli():
    parser = argparse.ArgumentParser(
        description=(
            "Safety-rail management for the harness invoke loop. Record "
            "failures, inspect the kill switch, or clear session state."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="Record one failure and maybe trip the kill switch.")
    record.add_argument("--category", required=True, help="Failure category (scope_violation/ambiguity/...).")
    record.add_argument("--unit-id", default=None, help="Unit ID for the failure entry.")
    record.add_argument("--root", type=Path, default=None, help="Harness root (default: find_harness_root).")

    status = sub.add_parser("status", help="Print current safety-rail status as JSON.")
    status.add_argument("--root", type=Path, default=None)

    clear = sub.add_parser("clear", help="Clear the kill switch + failure log (idempotent).")
    clear.add_argument("--root", type=Path, default=None)

    args = parser.parse_args()

    root = args.root or find_harness_root()
    if root is None:
        print("Error: no harness root found.", file=sys.stderr)
        sys.exit(1)

    if args.command == "record":
        tripped = record_failure(Path(root), args.category, unit_id=args.unit_id)
        print(json.dumps({
            "category": args.category,
            "unit_id": args.unit_id,
            "kill_switch_tripped": tripped,
            "currently_disabled": is_parallel_disabled(Path(root)),
            "session_failure_count": _count_session_failures(_failures_path(Path(root))),
        }, indent=2, ensure_ascii=False))
    elif args.command == "status":
        print(json.dumps({
            "parallel_disabled": is_parallel_disabled(Path(root)),
            "session_failure_count": _count_session_failures(_failures_path(Path(root))),
        }, indent=2, ensure_ascii=False))
    elif args.command == "clear":
        clear_safety_rails(Path(root))
        print(json.dumps({"cleared": True}, indent=2, ensure_ascii=False))

    sys.exit(0)


if __name__ == "__main__":
    _cli()
