#!/usr/bin/env python3
"""Compute a parallel-safe batch of units from a frontier.

Consumes the JSON frontier produced by `select_next_unit.py --frontier` and
the `execution_mode.parallelism` block in `config.json`. Emits a JSON object
with three keys:

  * ``batch``      -- units selected to run concurrently.
  * ``excluded``   -- units dropped, each carrying a machine-readable reason.
  * ``batch_id``   -- UTC-timestamp identifier for the decision.

Exclusion reason values (exact strings):

  * ``not_parallel_safe``         -- ``parallel_safe`` is false on the unit,
                                     or ``require_touches_paths`` is true and
                                     the unit has no ``touches_paths``.
  * ``path_overlap_with:<unit_id>`` -- the unit's ``touches_paths`` overlaps
                                     with a unit already in the batch.
  * ``capacity_cap``              -- the batch is already at
                                     ``max_concurrent_units``.

Selection is a single left-to-right greedy pack in the order the frontier
was produced. This keeps the result deterministic given the same inputs
and mirrors the left-to-right semantics of the selector.

The glob-overlap check uses stdlib ``fnmatch`` plus a literal-prefix
heuristic for two-wildcard pairs: two patterns overlap when one's literal
prefix is a prefix of the other's, since every path matching the more-
specific pattern also matches the more-general one. The heuristic errs on
the side of serialising potentially-overlapping pairs -- a false overlap
means one unit runs after the other, never data corruption.

Uses only Python 3 stdlib. Imports from harness_utils.
"""
import argparse
import fnmatch
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from harness_utils import find_harness_root


WILDCARD_CHARS = ("*", "?", "[")


def _is_literal(pattern):
    return not any(c in pattern for c in WILDCARD_CHARS)


def _literal_prefix(pattern):
    """Return the pattern's literal prefix (everything before the first wildcard)."""
    idx = len(pattern)
    for c in WILDCARD_CHARS:
        pos = pattern.find(c)
        if pos != -1 and pos < idx:
            idx = pos
    return pattern[:idx]


def _patterns_overlap(a, b):
    """Return True when two repo-relative glob patterns share any matching path.

    Literal/literal: exact match.
    Literal/glob: ``fnmatch`` the literal against the glob.
    Glob/glob: literal-prefix containment (pessimistic: false positives are
    treated as an overlap, which only costs parallelism).
    """
    if _is_literal(a) and _is_literal(b):
        return a == b
    if _is_literal(a):
        return fnmatch.fnmatchcase(a, b)
    if _is_literal(b):
        return fnmatch.fnmatchcase(b, a)
    prefix_a = _literal_prefix(a)
    prefix_b = _literal_prefix(b)
    # Treat empty-prefix globs ('*', '**') as matching everything.
    if not prefix_a or not prefix_b:
        return True
    return prefix_a.startswith(prefix_b) or prefix_b.startswith(prefix_a)


def _unit_pair_overlaps(a_paths, b_paths):
    for pa in a_paths or []:
        for pb in b_paths or []:
            if _patterns_overlap(pa, pb):
                return True
    return False


def _parallelism_config(config):
    """Extract the parallelism block from a config.json dict.

    Defaults are conservative and match schemas/config.json.
    """
    execution_mode = config.get("execution_mode") or {}
    if not isinstance(execution_mode, dict):
        execution_mode = {}
    parallelism = execution_mode.get("parallelism") or {}
    return {
        "enabled": bool(parallelism.get("enabled", False)),
        "max_concurrent_units": int(parallelism.get("max_concurrent_units", 3)),
        "conflict_strategy": parallelism.get("conflict_strategy", "abort_batch"),
        "require_touches_paths": bool(parallelism.get("require_touches_paths", True)),
        "allow_cross_phase": bool(parallelism.get("allow_cross_phase", False)),
    }


def _make_batch_id(now=None):
    moment = now or datetime.now(timezone.utc)
    return "batch_" + moment.strftime("%Y-%m-%dT%H-%M-%SZ")


def compute_batch(frontier, parallelism, now=None):
    """Apply the greedy-pack algorithm to a frontier.

    Args:
      frontier: list of unit dicts (as emitted by ``select_next_unit.py
        --frontier``). Must carry ``id``, ``parallel_safe``, and
        ``touches_paths``.
      parallelism: dict from ``_parallelism_config``.
      now: optional ``datetime`` for deterministic batch_id in tests.

    Returns:
      ``{"batch_id", "batch", "excluded"}`` where ``batch`` is a list of unit
      dicts (left in the order they were accepted) and ``excluded`` is a list
      of ``{"unit_id", "reason"}`` dicts preserving the frontier's order.

    Respects ``allow_cross_phase``: when false, the batch is restricted to
    the phase of the first accepted unit; later frontier entries from other
    phases are skipped without an excluded entry (they remain eligible for
    future batches).
    """
    max_concurrent = max(1, parallelism.get("max_concurrent_units", 3))
    require_paths = parallelism.get("require_touches_paths", True)
    allow_cross_phase = parallelism.get("allow_cross_phase", False)

    batch = []
    excluded = []
    batch_phase_id = None

    for unit in frontier:
        unit_id = unit.get("id", "")
        parallel_safe = bool(unit.get("parallel_safe", False))
        touches = list(unit.get("touches_paths") or [])

        if not parallel_safe or (require_paths and not touches):
            excluded.append({"unit_id": unit_id, "reason": "not_parallel_safe"})
            continue

        if not allow_cross_phase and batch_phase_id is not None:
            if unit.get("phase_id") != batch_phase_id:
                # Defer cross-phase units to a later batch without an
                # "exclusion" record -- they aren't being rejected.
                continue

        if len(batch) >= max_concurrent:
            excluded.append({"unit_id": unit_id, "reason": "capacity_cap"})
            continue

        conflict_with = None
        for accepted in batch:
            if _unit_pair_overlaps(touches, accepted.get("touches_paths")):
                conflict_with = accepted.get("id", "")
                break

        if conflict_with is not None:
            excluded.append(
                {"unit_id": unit_id, "reason": f"path_overlap_with:{conflict_with}"}
            )
            continue

        batch.append(unit)
        if batch_phase_id is None:
            batch_phase_id = unit.get("phase_id")

    return {
        "batch_id": _make_batch_id(now),
        "batch": batch,
        "excluded": excluded,
    }


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Greedy-pack a parallel-safe batch from a frontier. Emits "
            "{batch, excluded, batch_id} with machine-readable exclusion reasons."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to frontier JSON (list of units from select_next_unit.py --frontier).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.json (default: .harness/config.json under the harness root).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Harness root (default: find via find_harness_root).",
    )
    args = parser.parse_args()

    root = args.root or find_harness_root()
    config_path = args.config
    if config_path is None:
        if root is None:
            print(
                "Error: --config not provided and no harness root found.",
                file=sys.stderr,
            )
            sys.exit(1)
        config_path = Path(root) / ".harness" / "config.json"

    if not args.input.exists():
        print(f"Error: frontier file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    if not Path(config_path).exists():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    frontier = _read_json(args.input)
    if not isinstance(frontier, list):
        print("Error: frontier must be a JSON array of unit objects.", file=sys.stderr)
        sys.exit(1)
    config = _read_json(config_path)

    result = compute_batch(frontier, _parallelism_config(config))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
