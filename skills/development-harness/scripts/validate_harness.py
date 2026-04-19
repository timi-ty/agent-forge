#!/usr/bin/env python3
"""Validate the structural integrity of harness data files.

Uses only Python 3 stdlib. Imports from harness_utils.
"""
import argparse
import json
import sys
from pathlib import Path

from harness_utils import (
    SCHEMA_VERSION,
    check_schema_version,
    find_harness_root,
    validate_required_keys,
)

REQUIRED_FILES = [
    "config.json",
    "manifest.json",
    "state.json",
    "phase-graph.json",
    "checkpoint.md",
]
PHASES_DIR = "PHASES"

FLEET_MODE_ENUM = {"idle", "dispatched", "merging"}
REQUIRED_UNIT_KEYS = {"id", "description", "status", "depends_on", "parallel_safe"}


def _read_json_safe(filepath):
    """Read and parse JSON. Return (data, error). error is None on success."""
    filepath = Path(filepath)
    if not filepath.exists():
        return None, f"{filepath}: file not found"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"{filepath}: invalid JSON: {e}"


def _is_touches_path_safe(path):
    """Return True if a touches_paths entry is repo-relative and contains no traversal.

    Rejects:
      - non-string or empty values
      - POSIX-absolute paths (leading '/')
      - Windows-absolute paths (e.g. 'C:/foo', 'C:\\foo')
      - any '..' segment after normalising separators
    """
    if not isinstance(path, str) or not path:
        return False
    normalized = path.replace("\\", "/")
    if normalized.startswith("/"):
        return False
    if len(normalized) >= 2 and normalized[1] == ":":
        return False
    segments = [seg for seg in normalized.split("/") if seg != ""]
    if ".." in segments:
        return False
    return True


def _find_cycle(graph):
    """Detect a dependency cycle in a directed graph.

    Args:
      graph: dict mapping node_id -> list of node_ids it depends on.

    Returns:
      List of node_ids forming a cycle (first node repeated at the end to
      close the path), or None if the graph is acyclic.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}
    path = []

    def visit(node):
        if color[node] == GRAY:
            start = path.index(node)
            return path[start:] + [node]
        if color[node] == BLACK:
            return None
        color[node] = GRAY
        path.append(node)
        for dep in graph.get(node, []) or []:
            if dep not in graph:
                continue
            cycle = visit(dep)
            if cycle is not None:
                return cycle
        path.pop()
        color[node] = BLACK
        return None

    for node in sorted(graph.keys()):
        if color[node] == WHITE:
            cycle = visit(node)
            if cycle is not None:
                return cycle
    return None


def _validate_manifest(data, filepath):
    """Validate manifest.json structure."""
    errors = []
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        errors.append(f"{filepath}: entries must be an array")
        return errors
    required_entry_keys = {"path", "ownership", "type", "removable"}
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"{filepath}: entries[{i}] must be an object")
            continue
        missing = required_entry_keys - set(entry.keys())
        if missing:
            errors.append(f"{filepath}: entries[{i}] missing: {', '.join(sorted(missing))}")
    return errors


def _validate_unit(unit, phase_index, unit_index, filepath):
    """Validate a single unit dict against v2 required-field rules."""
    errors = []
    locator = f"{filepath}: phases[{phase_index}].units[{unit_index}]"
    if not isinstance(unit, dict):
        errors.append(f"{locator} must be an object")
        return errors

    missing = REQUIRED_UNIT_KEYS - set(unit.keys())
    if missing:
        errors.append(f"{locator} missing: {', '.join(sorted(missing))}")

    if "depends_on" in unit and not isinstance(unit.get("depends_on"), list):
        errors.append(f"{locator}.depends_on must be an array")

    if "parallel_safe" in unit and not isinstance(unit.get("parallel_safe"), bool):
        errors.append(f"{locator}.parallel_safe must be a boolean")

    parallel_safe = unit.get("parallel_safe")
    touches_paths = unit.get("touches_paths")

    if parallel_safe is True:
        if touches_paths is None:
            errors.append(
                f"{locator} declares parallel_safe: true but is missing touches_paths "
                f"(required for parallel-eligible units)"
            )
        elif not isinstance(touches_paths, list) or len(touches_paths) == 0:
            errors.append(
                f"{locator}.touches_paths must be a non-empty array when parallel_safe is true"
            )

    if touches_paths is not None:
        if not isinstance(touches_paths, list):
            errors.append(f"{locator}.touches_paths must be an array")
        else:
            for j, path in enumerate(touches_paths):
                if not _is_touches_path_safe(path):
                    errors.append(
                        f"{locator}.touches_paths[{j}] is unsafe "
                        f"(must be a non-empty repo-relative path without '..' or drive/root prefix): {path!r}"
                    )
    return errors


def _validate_phase_graph(data, filepath):
    """Validate phase-graph.json structure, including unit-level v2 fields and cycles."""
    errors = []
    phases = data.get("phases")
    if phases is None:
        errors.append(f"{filepath}: missing phases")
        return errors
    if not isinstance(phases, list):
        errors.append(f"{filepath}: phases must be an array")
        return errors

    required_phase_keys = {"id", "slug", "status", "depends_on", "units"}
    phase_graph = {}
    unit_graph = {}
    known_phase_ids = set()
    known_unit_ids = set()

    for i, phase in enumerate(phases):
        if not isinstance(phase, dict):
            errors.append(f"{filepath}: phases[{i}] must be an object")
            continue
        missing = required_phase_keys - set(phase.keys())
        if missing:
            errors.append(f"{filepath}: phases[{i}] missing: {', '.join(sorted(missing))}")
            continue
        if not isinstance(phase.get("depends_on"), list):
            errors.append(f"{filepath}: phases[{i}].depends_on must be an array")
            continue
        if not isinstance(phase.get("units"), list):
            errors.append(f"{filepath}: phases[{i}].units must be an array")
            continue

        phase_id = phase["id"]
        known_phase_ids.add(phase_id)
        phase_graph[phase_id] = list(phase.get("depends_on", []))

        for j, unit in enumerate(phase.get("units", [])):
            errors.extend(_validate_unit(unit, i, j, filepath))
            if isinstance(unit, dict) and isinstance(unit.get("id"), str):
                unit_id = unit["id"]
                known_unit_ids.add(unit_id)
                deps = unit.get("depends_on")
                unit_graph[unit_id] = list(deps) if isinstance(deps, list) else []

    # Referential integrity for phase-level depends_on.
    for phase_id, deps in phase_graph.items():
        for dep in deps:
            if dep not in known_phase_ids:
                errors.append(
                    f"{filepath}: phase {phase_id!r} depends_on unknown phase {dep!r}"
                )

    # Referential integrity for unit-level depends_on.
    for unit_id, deps in unit_graph.items():
        for dep in deps:
            if dep not in known_unit_ids:
                errors.append(
                    f"{filepath}: unit {unit_id!r} depends_on unknown unit {dep!r}"
                )

    # Cycle detection.
    phase_cycle = _find_cycle(phase_graph)
    if phase_cycle:
        errors.append(
            f"{filepath}: phase depends_on cycle detected: {' -> '.join(phase_cycle)}"
        )
    unit_cycle = _find_cycle(unit_graph)
    if unit_cycle:
        errors.append(
            f"{filepath}: unit depends_on cycle detected: {' -> '.join(unit_cycle)}"
        )

    return errors


def _validate_state(data, filepath):
    """Validate state.json structure, including fleet.mode enum when fleet is present."""
    errors = []
    if "execution" not in data:
        errors.append(f"{filepath}: missing execution section")
    if "checkpoint" not in data:
        errors.append(f"{filepath}: missing checkpoint section")

    execution = data.get("execution")
    if isinstance(execution, dict) and "fleet" in execution:
        fleet = execution["fleet"]
        if not isinstance(fleet, dict):
            errors.append(f"{filepath}: execution.fleet must be an object")
        else:
            mode = fleet.get("mode")
            if mode is None:
                errors.append(f"{filepath}: execution.fleet.mode is required")
            elif mode not in FLEET_MODE_ENUM:
                errors.append(
                    f"{filepath}: execution.fleet.mode must be one of "
                    f"{sorted(FLEET_MODE_ENUM)}, got {mode!r}"
                )
    return errors


def run_validation(root):
    """Run full harness validation. Return dict with valid, errors, warnings."""
    errors = []
    warnings = []
    root = Path(root)
    harness_dir = root / ".harness"

    # 1. Check .harness/ exists
    if not harness_dir.is_dir():
        errors.append(".harness/ directory not found")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # 2. Validate each required file exists
    for name in REQUIRED_FILES:
        p = harness_dir / name
        if not p.exists():
            errors.append(f"Required file missing: .harness/{name}")

    # 3. Validate JSON files
    json_files = {
        "config.json": {
            "required_keys": ["schema_version", "project", "stack", "deployment", "git", "testing", "quality"],
        },
        "manifest.json": {
            "required_keys": ["schema_version", "entries"],
            "extra_validator": _validate_manifest,
        },
        "state.json": {
            "required_keys": ["schema_version", "execution", "checkpoint"],
            "extra_validator": _validate_state,
        },
        "phase-graph.json": {
            "required_keys": ["schema_version", "phases"],
            "extra_validator": _validate_phase_graph,
        },
    }

    for filename, spec in json_files.items():
        filepath = harness_dir / filename
        if not filepath.exists():
            continue  # already reported as missing
        data, err = _read_json_safe(filepath)
        if err:
            errors.append(err)
            continue
        # schema_version
        sv_result = check_schema_version(data, SCHEMA_VERSION, f".harness/{filename}")
        if not sv_result["valid"]:
            errors.append(sv_result["error"])
        # required keys
        rk_result = validate_required_keys(data, spec["required_keys"], f".harness/{filename}")
        if not rk_result["valid"]:
            errors.append(rk_result["error"])
        # extra validator
        if "extra_validator" in spec:
            errors.extend(spec["extra_validator"](data, f".harness/{filename}"))

    # 7. Check PHASES/ directory exists
    phases_dir = root / PHASES_DIR
    if not phases_dir.is_dir():
        errors.append(f"{PHASES_DIR}/ directory not found")

    valid = len(errors) == 0
    return {"valid": valid, "errors": errors, "warnings": warnings}


def main():
    parser = argparse.ArgumentParser(description="Validate harness structural integrity")
    parser.add_argument("--root", type=Path, default=None, help="Harness root (default: find via find_harness_root)")
    args = parser.parse_args()

    root = args.root or find_harness_root()
    if root is None:
        result = {"valid": False, "errors": [".harness/ directory not found"], "warnings": []}
    else:
        result = run_validation(root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
