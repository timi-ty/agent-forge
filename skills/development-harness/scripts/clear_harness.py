#!/usr/bin/env python3
"""Clear harness artifacts per manifest.json.

Reads manifest.json and generates a dry-run deletion report, or executes deletion.
Uses only Python 3 stdlib. Imports from harness_utils.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from harness_utils import (
    find_harness_root,
    read_json,
    read_text,
    remove_managed_block,
)

HARNESS_OWNED = "harness-owned"
MANAGED_BLOCK = "managed-block"
PRODUCT_OWNED = "product-owned"


def _resolve_root(args):
    """Resolve harness root from --root or find_harness_root."""
    if args.root:
        root = Path(args.root).resolve()
        if not (root / ".harness").is_dir():
            print("Error: --root must point to a directory containing .harness/", file=sys.stderr)
            sys.exit(1)
        return root
    root = find_harness_root()
    if root is None:
        print("Error: no .harness/ directory found.", file=sys.stderr)
        sys.exit(1)
    return Path(root)


def _load_manifest(root):
    """Load manifest.json. Exit on missing or corrupt."""
    manifest_path = root / ".harness" / "manifest.json"
    if not manifest_path.exists():
        print("Error: manifest not found:", manifest_path, file=sys.stderr)
        sys.exit(1)
    return read_json(manifest_path)


def _resolve_path(root, entry_path):
    """Resolve manifest path (may have trailing slash) to absolute Path."""
    p = entry_path.rstrip("/")
    return (root / p).resolve()


def _list_dir_recursive(dir_path):
    """Recursively list all files and subdirs under dir_path."""
    items = []
    try:
        for item in dir_path.rglob("*"):
            items.append(item)
        items.sort(key=lambda x: (len(x.parts), str(x)))
    except PermissionError:
        pass
    return items


def _build_report(root, manifest):
    """Build dry-run report from manifest entries."""
    entries = manifest.get("entries", [])
    if not isinstance(entries, list):
        return {"error": "manifest entries must be an array"}

    will_delete = []
    will_remove_block = []
    will_preserve = []
    warnings = []

    for entry in entries:
        if not isinstance(entry, dict):
            warnings.append("Skipping invalid entry (not an object)")
            continue

        path_str = entry.get("path")
        ownership = entry.get("ownership")

        if not path_str:
            warnings.append("Skipping entry with missing path")
            continue

        abs_path = _resolve_path(root, path_str)

        if ownership == PRODUCT_OWNED:
            will_preserve.append({"path": path_str, "note": "product-owned"})
            continue

        if ownership == MANAGED_BLOCK:
            if not abs_path.exists():
                warnings.append(f"Managed-block path does not exist: {path_str}")
                continue
            content = read_text(abs_path)
            if content is None:
                warnings.append(f"Cannot read managed-block file: {path_str}")
                continue
            _, block_found = remove_managed_block(content)
            will_remove_block.append({"path": path_str, "block_found": block_found})
            continue

        if ownership == HARNESS_OWNED:
            if not abs_path.exists():
                warnings.append(f"Harness-owned path does not exist: {path_str}")
                continue
            entry_type = entry.get("type", "unknown")
            if abs_path.is_dir():
                contents = [str(p.relative_to(root)) for p in _list_dir_recursive(abs_path)]
                will_delete.append({
                    "path": path_str,
                    "type": "directory",
                    "exists": True,
                    "contents": contents,
                })
            else:
                will_delete.append({"path": path_str, "type": entry_type, "exists": True})
            continue

        warnings.append(f"Unknown ownership class '{ownership}' for path: {path_str}")

    return {
        "mode": "dry-run",
        "will_delete": will_delete,
        "will_remove_block": will_remove_block,
        "will_preserve": will_preserve,
        "warnings": warnings,
    }


def _execute_deletion(root, report):
    """Execute deletion based on report. Mutates report to set mode='execute'."""
    report["mode"] = "execute"
    deleted_count = 0
    block_removed_count = 0
    errors = []

    for item in report["will_delete"]:
        path_str = item["path"]
        abs_path = _resolve_path(root, path_str)
        if not abs_path.exists():
            continue
        try:
            if abs_path.is_dir():
                shutil.rmtree(abs_path)
            else:
                abs_path.unlink()
            deleted_count += 1
        except PermissionError as e:
            errors.append(f"Permission error deleting {path_str}: {e}")
        except OSError as e:
            errors.append(f"Error deleting {path_str}: {e}")

    for item in report["will_remove_block"]:
        path_str = item["path"]
        abs_path = _resolve_path(root, path_str)
        if not abs_path.exists():
            continue
        content = read_text(abs_path)
        if content is None:
            errors.append(f"Cannot read {path_str}")
            continue
        new_content, block_found = remove_managed_block(content)
        if block_found:
            try:
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                block_removed_count += 1
            except (PermissionError, OSError) as e:
                errors.append(f"Error writing {path_str}: {e}")

    if errors:
        report["errors"] = errors
        for err in errors:
            print(err, file=sys.stderr)

    print(f"Deleted {deleted_count} harness-owned path(s).")
    print(f"Removed {block_removed_count} managed block(s).")
    return report


def main():
    parser = argparse.ArgumentParser(description="Clear harness artifacts per manifest")
    parser.add_argument("--root", type=str, help="Harness root directory (default: auto-detect)")
    parser.add_argument("--execute", action="store_true", help="Execute deletion (default: dry-run)")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    root = _resolve_root(args)
    manifest = _load_manifest(root)
    report = _build_report(root, manifest)

    if "error" in report:
        print(report["error"], file=sys.stderr)
        sys.exit(1)

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.execute:
        if not args.force:
            print("\nAre you sure you want to delete these items? (y/N): ", end="", flush=True)
            try:
                resp = input().strip().lower()
            except EOFError:
                resp = ""
            if resp not in ("y", "yes"):
                print("Aborted.")
                sys.exit(0)
        _execute_deletion(root, report)


if __name__ == "__main__":
    main()
