#!/usr/bin/env python3
"""Shared utilities for development harness scripts.

Uses only Python 3 stdlib. No external dependencies.
"""
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

HARNESS_DIR = ".harness"
SCHEMA_VERSION = "2.0"

MANAGED_BLOCK_START = "<!-- HARNESS:START -->"
MANAGED_BLOCK_END = "<!-- HARNESS:END -->"


def find_harness_root(start_path=None):
    """Walk up from start_path to find the directory containing .harness/."""
    path = Path(start_path or os.getcwd()).resolve()
    while path != path.parent:
        if (path / HARNESS_DIR).is_dir():
            return path
        path = path.parent
    return None


def harness_path(filename, root=None):
    """Return absolute path to a file inside .harness/."""
    root = root or find_harness_root()
    if root is None:
        print("Error: no .harness/ directory found.", file=sys.stderr)
        sys.exit(1)
    return Path(root) / HARNESS_DIR / filename


def read_json(filepath):
    """Read and parse a JSON file. Exit with error if invalid."""
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {filepath}: {e}", file=sys.stderr)
        sys.exit(1)


def write_json(filepath, data, indent=2):
    """Write data as formatted JSON."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
        f.write("\n")


def read_text(filepath):
    """Read a text file. Return None if not found."""
    filepath = Path(filepath)
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def write_text(filepath, content):
    """Write text to a file, creating parent dirs if needed."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def now_iso():
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_schema_version(data, expected=SCHEMA_VERSION, filepath="unknown"):
    """Validate that a loaded JSON object has the expected schema_version.

    On mismatch, the error message directs the user to re-run
    /create-development-harness. No in-place migration is provided by design.
    """
    version = data.get("schema_version")
    if version is None:
        return {
            "valid": False,
            "error": (
                f"{filepath}: missing schema_version. "
                f"Re-run /create-development-harness to regenerate harness files at schema v{expected}."
            ),
        }
    if version != expected:
        return {
            "valid": False,
            "error": (
                f"{filepath}: schema_version is '{version}', expected '{expected}'. "
                f"Re-run /create-development-harness to regenerate harness files at schema v{expected}."
            ),
        }
    return {"valid": True, "error": None}


def validate_required_keys(data, required_keys, filepath="unknown"):
    """Check that all required top-level keys exist."""
    missing = [k for k in required_keys if k not in data]
    if missing:
        return {
            "valid": False,
            "error": f"{filepath}: missing required keys: {', '.join(missing)}",
        }
    return {"valid": True, "error": None}


def insert_managed_block(content, block_text):
    """Insert or replace a managed block in text content.

    If HARNESS:START/END markers exist, replace the block between them.
    If not, append the block at the end.
    Returns the updated content.
    """
    pattern = re.compile(
        rf"{re.escape(MANAGED_BLOCK_START)}.*?{re.escape(MANAGED_BLOCK_END)}",
        re.DOTALL,
    )
    new_block = f"{MANAGED_BLOCK_START}\n{block_text}\n{MANAGED_BLOCK_END}"

    if pattern.search(content):
        return pattern.sub(new_block, content)
    else:
        separator = "\n\n" if content and not content.endswith("\n\n") else "\n" if content and not content.endswith("\n") else ""
        return content + separator + new_block + "\n"


def remove_managed_block(content):
    """Remove a managed block from text content.

    Returns (updated_content, block_was_found).
    """
    pattern = re.compile(
        rf"\n*{re.escape(MANAGED_BLOCK_START)}.*?{re.escape(MANAGED_BLOCK_END)}\n*",
        re.DOTALL,
    )
    new_content, count = pattern.subn("\n", content)
    return new_content.rstrip("\n") + "\n" if count > 0 else content, count > 0
