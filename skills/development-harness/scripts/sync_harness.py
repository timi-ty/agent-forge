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
import subprocess
import sys
from pathlib import Path

from harness_utils import find_harness_root, now_iso


HARNESS_DIR = ".harness"
WORKTREES_DIR = "worktrees"
BATCH_BRANCH_PREFIX = "harness/"


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


def _list_on_disk_worktrees(root):
    """Return ``[(batch_id, unit_id, relpath), ...]`` for every per-unit
    worktree directory under ``.harness/worktrees/<batch>/<unit>/``.

    Missing parent dir is not an error -- the list is just empty.
    """
    base = Path(root) / HARNESS_DIR / WORKTREES_DIR
    if not base.is_dir():
        return []
    found = []
    for batch_dir in sorted(base.iterdir()):
        if not batch_dir.is_dir():
            continue
        for unit_dir in sorted(batch_dir.iterdir()):
            if not unit_dir.is_dir():
                continue
            relpath = f"{HARNESS_DIR}/{WORKTREES_DIR}/{batch_dir.name}/{unit_dir.name}"
            found.append((batch_dir.name, unit_dir.name, relpath))
    return found


def _list_harness_branches(root):
    """Return every local branch matching ``harness/batch_*/``.

    Silently returns an empty list when git is unavailable or the
    directory isn't a git repo -- sync is informational, not critical.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "branch", "--list",
             "--format=%(refname:short)"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return []
    if result.returncode != 0:
        return []
    branches = []
    for line in result.stdout.splitlines():
        name = line.strip()
        if not name.startswith(BATCH_BRANCH_PREFIX):
            continue
        rest = name[len(BATCH_BRANCH_PREFIX):]
        if "/" not in rest:
            continue
        batch_id, _, unit_id = rest.partition("/")
        # Keep only names that look like harness/<batch_*>/<unit_id>.
        if not batch_id.startswith("batch_") or not unit_id:
            continue
        branches.append((batch_id, unit_id, name))
    return branches


def _detect_fleet_drift(root, state):
    """Report divergences between state.execution.fleet and git/disk reality.

    Three categories:
      * ``orphan_worktree`` -- directory under ``.harness/worktrees/`` has
        no matching fleet entry (by worktree_path).
      * ``stale_fleet_entry`` -- fleet entry whose worktree_path is not
        present on disk.
      * ``orphan_branch`` -- local git branch ``harness/batch_*/<unit>``
        with no matching fleet entry (by branch name).

    Each divergence carries the ids needed to act on it (feed to
    teardown_batch --batch-id, re-dispatch, etc.).
    """
    execution = (state or {}).get("execution") or {}
    fleet = execution.get("fleet") or {}
    units = fleet.get("units") or []

    known_worktrees = {u.get("worktree_path") for u in units if u.get("worktree_path")}
    known_branches = {u.get("branch") for u in units if u.get("branch")}

    divergences = []

    for batch_id, unit_id, relpath in _list_on_disk_worktrees(root):
        if relpath not in known_worktrees:
            divergences.append({
                "type": "orphan_worktree",
                "worktree_path": relpath,
                "batch_id": batch_id,
                "unit_id": unit_id,
            })

    for unit in units:
        worktree_path = unit.get("worktree_path")
        if not worktree_path:
            continue
        if not (Path(root) / worktree_path).is_dir():
            divergences.append({
                "type": "stale_fleet_entry",
                "unit_id": unit.get("unit_id"),
                "worktree_path": worktree_path,
                "branch": unit.get("branch"),
                "batch_id": fleet.get("batch_id"),
            })

    for batch_id, unit_id, branch in _list_harness_branches(root):
        if branch not in known_branches:
            divergences.append({
                "type": "orphan_branch",
                "branch": branch,
                "batch_id": batch_id,
                "unit_id": unit_id,
            })

    return divergences


def run_sync(root):
    """Run sync analysis. Return output dict."""
    root = Path(root).resolve()
    harness_dir = root / ".harness"
    phase_graph_path = harness_dir / "phase-graph.json"
    config_path = harness_dir / "config.json"
    state_path = harness_dir / "state.json"

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

    # Load state.json (optional). Used for fleet-drift detection below.
    state_data, _ = _read_json_safe(state_path)

    phases = pg_data.get("phases", [])
    all_paths = list(walk_project_tree(root))

    for phase in phases:
        report = build_phase_report(phase, all_paths)
        phase_reports.append(report)

    # Fleet-drift detection (unit_024): orphan worktrees / stale fleet
    # entries / orphan harness/batch_*/ branches.
    divergences.extend(_detect_fleet_drift(root, state_data or {}))

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
