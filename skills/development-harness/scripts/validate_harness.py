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


def _validate_phase_graph(data, filepath):
    """Validate phase-graph.json structure."""
    errors = []
    phases = data.get("phases")
    if phases is None:
        errors.append(f"{filepath}: missing phases")
        return errors
    if not isinstance(phases, list):
        errors.append(f"{filepath}: phases must be an array")
        return errors
    required_phase_keys = {"id", "slug", "status", "depends_on", "units"}
    for i, phase in enumerate(phases):
        if not isinstance(phase, dict):
            errors.append(f"{filepath}: phases[{i}] must be an object")
            continue
        missing = required_phase_keys - set(phase.keys())
        if missing:
            errors.append(f"{filepath}: phases[{i}] missing: {', '.join(sorted(missing))}")
        elif not isinstance(phase.get("depends_on"), list):
            errors.append(f"{filepath}: phases[{i}].depends_on must be an array")
        elif not isinstance(phase.get("units"), list):
            errors.append(f"{filepath}: phases[{i}].units must be an array")
    return errors


def _validate_state(data, filepath):
    """Validate state.json structure."""
    errors = []
    if "execution" not in data:
        errors.append(f"{filepath}: missing execution section")
    if "checkpoint" not in data:
        errors.append(f"{filepath}: missing checkpoint section")
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
