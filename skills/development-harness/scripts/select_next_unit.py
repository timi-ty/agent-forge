#!/usr/bin/env python3
"""The authoritative 'what to do next' source for the development harness.

The stop hook depends on this script. Selection is deterministic and strictly
driven by the v2 phase-graph: phase-level `depends_on` gates a phase, and
unit-level `depends_on` gates a unit. A valid v2 harness is assumed — callers
should have run `validate_harness.py` first. There is no legacy list-order
fallback: malformed units raise an error rather than silently succeeding.

Two output modes:

- No-flag call: prints a single JSON object matching the v1 stop-hook contract
  (fields: found, phase_id, phase_slug, unit_id, unit_description,
  phase_complete, all_complete). This is the head of the frontier wrapped in
  the historical record shape.

- `--frontier [--max N]`: prints a JSON array of every ready unit, optionally
  capped at N entries. Used by `compute_parallel_batch.py` (PHASE_002) and the
  rewritten invoke flow (PHASE_007).

Uses only Python 3 stdlib. Imports from harness_utils.
"""
import argparse
import json
import sys
from pathlib import Path

from harness_utils import find_harness_root


REQUIRED_UNIT_KEYS_FOR_SELECTION = ("id", "status", "depends_on")


class MalformedPhaseGraph(ValueError):
    """Raised when the phase-graph does not conform to the v2 selection contract."""


def _read_json_safe(filepath):
    """Read and parse JSON. Return (data, error). error is None on success."""
    filepath = Path(filepath)
    if not filepath.exists():
        return None, f"file not found: {filepath}"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


def _empty_result():
    return {
        "found": False,
        "phase_id": None,
        "phase_slug": None,
        "unit_id": None,
        "unit_description": None,
        "phase_complete": False,
        "all_complete": True,
    }


def _phase_dependencies_met(phase, phase_status_by_id):
    for dep_id in phase.get("depends_on", []) or []:
        if phase_status_by_id.get(dep_id) != "completed":
            return False
    return True


def _assert_unit_shape(unit, phase_id, index):
    """Validate minimum selection-relevant fields on a unit. Raises on malformed input."""
    if not isinstance(unit, dict):
        raise MalformedPhaseGraph(
            f"{phase_id}.units[{index}] must be an object, got {type(unit).__name__}"
        )
    missing = [k for k in REQUIRED_UNIT_KEYS_FOR_SELECTION if k not in unit]
    if missing:
        locator = f"{phase_id}.units[{index}]"
        raise MalformedPhaseGraph(
            f"{locator} missing required field(s) for selection: {', '.join(missing)}. "
            "Run validate_harness.py -- the graph is not v2-conformant."
        )
    if not isinstance(unit.get("depends_on"), list):
        raise MalformedPhaseGraph(
            f"{phase_id}.units[{unit.get('id', index)}].depends_on must be an array"
        )


def compute_frontier(phases, max_items=None):
    """Return the list of units eligible to start right now.

    An eligible unit satisfies all of:
      * its phase has `status != 'completed'`
      * every phase in its phase's `depends_on` has `status == 'completed'`
      * its own `status != 'completed'`
      * every unit in its `depends_on` has `status == 'completed'` (looked up
        across every phase — unit IDs are globally unique in a valid v2 graph)

    Each entry is augmented with `phase_id` and `phase_slug` so consumers can
    render or dispatch without re-indexing the graph.

    Order is stable: phase-list order, then unit-list order within each phase.

    Raises MalformedPhaseGraph if any unit is missing a selection-relevant
    field (no silent inference).
    """
    phase_status_by_id = {p.get("id"): p.get("status", "pending") for p in phases}
    unit_status_by_id = {}
    for phase in phases:
        for index, unit in enumerate(phase.get("units") or []):
            _assert_unit_shape(unit, phase.get("id", "?"), index)
            unit_status_by_id[unit["id"]] = unit.get("status", "pending")

    frontier = []
    for phase in phases:
        phase_id = phase.get("id")
        phase_status = phase.get("status", "pending")
        if phase_status == "completed":
            continue
        if not _phase_dependencies_met(phase, phase_status_by_id):
            continue
        phase_slug = phase.get("slug", "")
        for unit in phase.get("units") or []:
            if unit.get("status") == "completed":
                continue
            if not all(
                unit_status_by_id.get(dep) == "completed"
                for dep in unit.get("depends_on", [])
            ):
                continue
            frontier.append(
                {
                    "phase_id": phase_id,
                    "phase_slug": phase_slug,
                    "id": unit["id"],
                    "description": unit.get("description", ""),
                    "status": unit.get("status", "pending"),
                    "depends_on": list(unit.get("depends_on", [])),
                    "touches_paths": list(unit.get("touches_paths", []))
                    if unit.get("touches_paths") is not None
                    else [],
                    "parallel_safe": unit.get("parallel_safe", False),
                }
            )
            if max_items is not None and len(frontier) >= max_items:
                return frontier
    return frontier


def _phase_completion_pending(phases, phase_status_by_id):
    """Return the phase_id of a phase whose units are all completed but whose
    phase-level status is not yet 'completed' and whose dependencies are met.
    The invoke flow treats this as a signal to run phase-completion review
    before launching the next unit.
    """
    for phase in phases:
        if phase.get("status") == "completed":
            continue
        if not _phase_dependencies_met(phase, phase_status_by_id):
            continue
        units = phase.get("units") or []
        if units and all(u.get("status") == "completed" for u in units):
            return phase.get("id")
    return None


def select_next_unit(root, phase_graph_path):
    """Head-of-frontier selector in v1 stop-hook JSON contract."""
    data, err = _read_json_safe(phase_graph_path)
    if err:
        return _empty_result()

    phases = data.get("phases") or []
    if not phases:
        return _empty_result()

    phase_status_by_id = {p.get("id"): p.get("status", "pending") for p in phases}
    frontier = compute_frontier(phases, max_items=1)
    phase_complete_pending = _phase_completion_pending(phases, phase_status_by_id)

    if not frontier:
        result = _empty_result()
        # Even with no frontier, a pending-completion phase takes precedence
        # over "everything is done" for the stop-hook signal.
        result["phase_complete"] = phase_complete_pending is not None
        if phase_complete_pending is not None:
            result["all_complete"] = False
        return result

    head = frontier[0]
    return {
        "found": True,
        "phase_id": head["phase_id"],
        "phase_slug": head["phase_slug"],
        "unit_id": head["id"],
        "unit_description": head["description"],
        "phase_complete": phase_complete_pending is not None,
        "all_complete": False,
    }


def _print_frontier(root, phase_graph_path, max_items):
    data, err = _read_json_safe(phase_graph_path)
    if err:
        print(json.dumps([], indent=2, ensure_ascii=False))
        return
    phases = data.get("phases") or []
    print(
        json.dumps(
            compute_frontier(phases, max_items=max_items),
            indent=2,
            ensure_ascii=False,
        )
    )


def main():
    parser = argparse.ArgumentParser(
        description="Select the next executable unit (authoritative source for stop hook)"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Harness root (default: find via find_harness_root)",
    )
    parser.add_argument(
        "--phase-graph",
        type=Path,
        default=None,
        help="Path to phase-graph.json (default: .harness/phase-graph.json)",
    )
    parser.add_argument(
        "--frontier",
        action="store_true",
        help="Print the full frontier (all ready units) as a JSON array instead "
        "of the single-unit stop-hook record.",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Cap the frontier size when --frontier is set. Ignored without --frontier.",
    )
    args = parser.parse_args()

    root = args.root or find_harness_root()
    phase_graph_path = (
        args.phase_graph or (Path(root) / ".harness" / "phase-graph.json")
        if root is not None
        else None
    )

    try:
        if args.frontier:
            if phase_graph_path is None:
                print(json.dumps([], indent=2, ensure_ascii=False))
            else:
                _print_frontier(root, phase_graph_path, args.max)
        else:
            if phase_graph_path is None:
                print(json.dumps(_empty_result(), indent=2, ensure_ascii=False))
            else:
                print(
                    json.dumps(
                        select_next_unit(root, phase_graph_path),
                        indent=2,
                        ensure_ascii=False,
                    )
                )
    except MalformedPhaseGraph as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
