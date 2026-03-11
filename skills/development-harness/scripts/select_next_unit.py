#!/usr/bin/env python3
"""The authoritative 'what to do next' source for the development harness.

The stop hook depends on this script. Deterministic selection of the next
executable unit based on phase dependencies and unit status.

Uses only Python 3 stdlib. Imports from harness_utils.
"""
import argparse
import json
import sys
from pathlib import Path

from harness_utils import find_harness_root


def _read_json_safe(filepath):
    """Read and parse JSON. Return (data, None) on success, (None, error_msg) on failure."""
    filepath = Path(filepath)
    if not filepath.exists():
        return None, f"file not found: {filepath}"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


def _is_phase_unblocked(phase, phase_status_by_id):
    """A phase is unblocked if all phases in depends_on have status 'completed'."""
    for dep_id in phase.get("depends_on", []):
        if phase_status_by_id.get(dep_id) != "completed":
            return False
    return True


def select_next_unit(root, phase_graph_path):
    """Determine the next executable unit. Returns output dict."""
    # Load phase-graph
    data, err = _read_json_safe(phase_graph_path)
    if err:
        return {
            "found": False,
            "phase_id": None,
            "phase_slug": None,
            "unit_id": None,
            "unit_description": None,
            "phase_complete": False,
            "all_complete": True,
        }

    phases = data.get("phases", [])
    if not phases:
        return {
            "found": False,
            "phase_id": None,
            "phase_slug": None,
            "unit_id": None,
            "unit_description": None,
            "phase_complete": False,
            "all_complete": True,
        }

    phase_status_by_id = {p["id"]: p.get("status", "pending") for p in phases}
    skipped_complete_phase = False

    for phase in phases:
        if not _is_phase_unblocked(phase, phase_status_by_id):
            continue

        phase_status = phase.get("status", "pending")
        phase_id = phase.get("id", "")
        phase_slug = phase.get("slug", "")
        units = phase.get("units", [])

        # Skip phases that are completed
        if phase_status == "completed":
            continue

        # All units in this phase are completed but phase not marked complete
        all_units_completed = all(u.get("status") == "completed" for u in units)
        if all_units_completed and units:
            skipped_complete_phase = True
            continue

        # Phase is unblocked and (in_progress or pending) with work to do
        # First, look for in_progress unit
        for unit in units:
            if unit.get("status") == "in_progress":
                return {
                    "found": True,
                    "phase_id": phase_id,
                    "phase_slug": phase_slug,
                    "unit_id": unit.get("id"),
                    "unit_description": unit.get("description"),
                    "phase_complete": skipped_complete_phase,
                    "all_complete": False,
                }

        # No in_progress unit; find first pending
        for unit in units:
            if unit.get("status") == "pending":
                return {
                    "found": True,
                    "phase_id": phase_id,
                    "phase_slug": phase_slug,
                    "unit_id": unit.get("id"),
                    "unit_description": unit.get("description"),
                    "phase_complete": skipped_complete_phase,
                    "all_complete": False,
                }

    # No executable unit found anywhere
    return {
        "found": False,
        "phase_id": None,
        "phase_slug": None,
        "unit_id": None,
        "unit_description": None,
        "phase_complete": False,
        "all_complete": True,
    }


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
    args = parser.parse_args()

    root = args.root or find_harness_root()
    if root is None:
        result = {
            "found": False,
            "phase_id": None,
            "phase_slug": None,
            "unit_id": None,
            "unit_description": None,
            "phase_complete": False,
            "all_complete": True,
        }
    else:
        phase_graph_path = args.phase_graph or (root / ".harness" / "phase-graph.json")
        result = select_next_unit(root, phase_graph_path)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
