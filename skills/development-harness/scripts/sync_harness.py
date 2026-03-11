#!/usr/bin/env python3
"""Compare phase-graph.json against actual file tree and report drift.

EVIDENCE-ONLY CLAIMING RULE: Only report "implemented" or "working" when there
is evidence: test file exists AND passes, build output exists, CI signal,
deploy check, or explicitly recorded validation_evidence in phase-graph.json.
Everything else is "present-but-unverified" or "unknown".

Keyword matching is heuristic and low-confidence. The agent must verify.

Uses only Python 3 stdlib. Imports from harness_utils.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from harness_utils import find_harness_root, now_iso, read_json


EXCLUDE_DIRS = {
    ".harness",
    ".cursor",
    ".git",
    "node_modules",
    "__pycache__",
    ".next",
    "dist",
    "build",
}

# Common test file patterns (heuristic)
TEST_PATTERNS = (
    r"test[_-].*\.(py|ts|tsx|js|jsx)$",
    r".*[_-]test\.(py|ts|tsx|js|jsx)$",
    r".*\.spec\.(ts|tsx|js|jsx)$",
    r".*\.test\.(ts|tsx|js|jsx)$",
)
TEST_REGEX = re.compile("|".join(f"({p})" for p in TEST_PATTERNS), re.IGNORECASE)


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


def _slug_to_keywords(slug):
    """Extract keyword tokens from a phase slug for heuristic matching."""
    # "auth-and-user-api" -> ["auth", "user", "api"]
    return [s for s in re.split(r"[-_\s]+", slug.lower()) if len(s) > 1]


def _is_test_file(path_str):
    """Heuristic: does this path look like a test file?"""
    return bool(TEST_REGEX.search(path_str))


def _path_matches_keywords(path_str, keywords):
    """Heuristic: does path contain any of the keywords? Low-confidence."""
    path_lower = path_str.lower().replace("\\", "/")
    return [kw for kw in keywords if kw in path_lower]


def walk_project_tree(root):
    """Walk project tree, yielding relative paths. Excludes EXCLUDE_DIRS."""
    root = Path(root).resolve()
    for path in root.rglob("*"):
        if path.is_file():
            try:
                rel = path.relative_to(root)
            except ValueError:
                continue
            parts = rel.parts
            if any(d in parts for d in EXCLUDE_DIRS):
                continue
            yield str(rel).replace("\\", "/")


def build_phase_report(phase, all_paths):
    """Build drift report for a single phase."""
    phase_id = phase.get("id", "")
    slug = phase.get("slug", "")
    current_status = phase.get("status", "pending")
    units = phase.get("units", [])

    keywords = _slug_to_keywords(slug)
    file_matches = []
    test_matches = []

    for path_str in all_paths:
        matched_kw = _path_matches_keywords(path_str, keywords)
        if matched_kw:
            if _is_test_file(path_str):
                test_matches.append({
                    "path": path_str,
                    "confidence": "keyword-match",
                    "note": "Heuristic: filename/path matches phase slug. Agent must verify.",
                })
            else:
                file_matches.append({
                    "path": path_str,
                    "confidence": "keyword-match",
                    "note": "Heuristic: filename/path matches phase slug. Agent must verify.",
                })

    # Evidence-only: check validation_evidence in units
    has_validation_evidence = any(
        unit.get("validation_evidence")
        for unit in units
    )

    if has_validation_evidence:
        evidence_status = "verified"
    elif file_matches or test_matches:
        evidence_status = "present-but-unverified"
    else:
        evidence_status = "unknown"

    # Recommendation
    if evidence_status == "verified" and current_status in ("in_progress", "completed"):
        recommendation = "status-looks-correct"
    elif evidence_status == "verified" and current_status == "pending":
        recommendation = "may-be-further-along"
    elif evidence_status in ("present-but-unverified", "unknown") and current_status in ("in_progress", "completed"):
        recommendation = "may-have-regressed"
    else:
        recommendation = "insufficient-data"

    return {
        "phase_id": phase_id,
        "slug": slug,
        "current_status": current_status,
        "file_matches": file_matches,
        "test_matches": test_matches,
        "evidence_status": evidence_status,
        "recommendation": recommendation,
    }


def run_sync(root):
    """Run sync analysis. Return output dict."""
    root = Path(root).resolve()
    harness_dir = root / ".harness"
    phase_graph_path = harness_dir / "phase-graph.json"
    config_path = harness_dir / "config.json"

    divergences = []
    phase_reports = []

    # Load phase-graph
    pg_data, err = _read_json_safe(phase_graph_path)
    if err:
        divergences.append({
            "type": "load_error",
            "message": f"phase-graph.json: {err}",
        })
        return {
            "sync_timestamp": now_iso(),
            "divergences": divergences,
            "phase_reports": phase_reports,
        }

    # Load config (optional)
    config_data, _ = _read_json_safe(config_path)

    phases = pg_data.get("phases", [])
    all_paths = list(walk_project_tree(root))

    for phase in phases:
        report = build_phase_report(phase, all_paths)
        phase_reports.append(report)

    return {
        "sync_timestamp": now_iso(),
        "divergences": divergences,
        "phase_reports": phase_reports,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Compare phase-graph against file tree and report drift"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Harness root (default: find via find_harness_root)",
    )
    args = parser.parse_args()

    root = args.root or find_harness_root()
    if root is None:
        result = {
            "sync_timestamp": now_iso(),
            "divergences": [{"type": "no_root", "message": ".harness/ directory not found"}],
            "phase_reports": [],
        }
    else:
        result = run_sync(root)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
