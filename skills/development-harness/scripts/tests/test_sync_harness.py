"""Tests for sync_harness.py via subprocess."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent dir so we can import from scripts if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SCRIPT_DIR = Path(__file__).resolve().parent.parent
SYNC_SCRIPT = SCRIPT_DIR / "sync_harness.py"


def run_sync_harness(root):
    """Run sync_harness.py and return (returncode, parsed JSON from stdout)."""
    result = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        cwd=str(SCRIPT_DIR),
    )
    try:
        output = json.loads(result.stdout) if result.stdout else {}
    except json.JSONDecodeError:
        output = {}
    return result.returncode, output


def _phase_graph_auth_system_no_evidence():
    """Phase 'auth-system' with 2 units, no validation_evidence."""
    return {
        "schema_version": "1.0",
        "phases": [
            {
                "id": "PHASE_001",
                "slug": "auth-system",
                "status": "in_progress",
                "depends_on": [],
                "units": [
                    {"id": "unit_001", "description": "Auth module", "status": "in_progress"},
                    {"id": "unit_002", "description": "Auth tests", "status": "pending"},
                ],
            },
        ],
    }


def _phase_graph_auth_system_with_evidence():
    """Phase 'auth-system' with validation_evidence in at least one unit."""
    return {
        "schema_version": "1.0",
        "phases": [
            {
                "id": "PHASE_001",
                "slug": "auth-system",
                "status": "in_progress",
                "depends_on": [],
                "units": [
                    {
                        "id": "unit_001",
                        "description": "Auth module",
                        "status": "in_progress",
                        "validation_evidence": ["Unit tests pass"],
                    },
                    {"id": "unit_002", "description": "Auth tests", "status": "pending"},
                ],
            },
        ],
    }


def _basic_config():
    return {
        "schema_version": "1.0",
        "project": {"name": "test"},
        "stack": {},
        "deployment": {},
        "git": {},
        "testing": {},
        "quality": {},
    }


class TestSyncHarness(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))

    def _create_workspace_with_auth_files(self, phase_graph=None):
        """Create workspace with phase-graph.json, config.json, src/auth.py, tests/test_auth.py."""
        if phase_graph is None:
            phase_graph = _phase_graph_auth_system_no_evidence()
        harness_dir = self.temp_dir / ".harness"
        harness_dir.mkdir()
        (harness_dir / "phase-graph.json").write_text(json.dumps(phase_graph, indent=2), encoding="utf-8")
        (harness_dir / "config.json").write_text(json.dumps(_basic_config(), indent=2), encoding="utf-8")
        (self.temp_dir / "src").mkdir()
        (self.temp_dir / "src" / "auth.py").write_text("# auth module\n", encoding="utf-8")
        (self.temp_dir / "tests").mkdir()
        (self.temp_dir / "tests" / "test_auth.py").write_text("# auth tests\n", encoding="utf-8")
        return self.temp_dir

    def test_produces_sync_report(self):
        root = self._create_workspace_with_auth_files()
        returncode, output = run_sync_harness(root)
        self.assertEqual(returncode, 0)
        self.assertIn("sync_timestamp", output)
        self.assertIn("phase_reports", output)
        self.assertIsInstance(output["phase_reports"], list)

    def test_reports_phase_evidence_status(self):
        root = self._create_workspace_with_auth_files()
        returncode, output = run_sync_harness(root)
        self.assertEqual(returncode, 0)
        phase_reports = output.get("phase_reports", [])
        self.assertGreater(len(phase_reports), 0)
        for report in phase_reports:
            self.assertIn("evidence_status", report)

    def test_unverified_without_evidence(self):
        """Units without validation_evidence are NOT marked 'verified'."""
        root = self._create_workspace_with_auth_files(
            phase_graph=_phase_graph_auth_system_no_evidence()
        )
        returncode, output = run_sync_harness(root)
        self.assertEqual(returncode, 0)
        phase_reports = output.get("phase_reports", [])
        self.assertGreater(len(phase_reports), 0)
        for report in phase_reports:
            # No unit has validation_evidence, so evidence_status must not be "verified"
            self.assertNotEqual(
                report.get("evidence_status"),
                "verified",
                "Phase without validation_evidence should not be marked verified",
            )


def _init_git_repo(root):
    """Minimal git repo with one commit, suitable for branch creation."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "sync@test.local"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Sync Test"], check=True
    )
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "initial"], check=True
    )


def _write_state_with_fleet(root, batch_id, units):
    """Write minimal state.json carrying a fleet block.

    Each `units` item is a dict with at least `unit_id`, `worktree_path`,
    and `branch`. Missing keys are tolerated so tests can exercise
    degenerate fleet entries.
    """
    harness_dir = root / ".harness"
    harness_dir.mkdir(exist_ok=True)
    state = {
        "schema_version": "1.0",
        "execution": {
            "fleet": {
                "mode": "dispatched",
                "batch_id": batch_id,
                "units": list(units),
            }
        },
    }
    (harness_dir / "state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )


def _minimal_phase_graph():
    """Phase-graph minimal enough for sync_harness to run without errors."""
    return {
        "schema_version": "1.0",
        "phases": [
            {
                "id": "PHASE_X",
                "slug": "fleet-fixture",
                "status": "in_progress",
                "depends_on": [],
                "units": [],
            }
        ],
    }


class TestFleetDriftDetection(unittest.TestCase):
    """unit_024: sync_harness reports orphan worktrees / stale fleet entries / orphan branches."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True)
        )
        _init_git_repo(self.temp_dir)
        # Seed a phase-graph so sync_harness doesn't bail early.
        harness_dir = self.temp_dir / ".harness"
        harness_dir.mkdir(exist_ok=True)
        (harness_dir / "phase-graph.json").write_text(
            json.dumps(_minimal_phase_graph(), indent=2), encoding="utf-8"
        )
        self.batch_id = "batch_2026-04-20T02-30-00Z"

    def _worktree_dir(self, batch_id, unit_id):
        wt = self.temp_dir / ".harness" / "worktrees" / batch_id / unit_id
        wt.mkdir(parents=True, exist_ok=True)
        # Drop a sentinel so it's a meaningful on-disk artifact (not just
        # an empty dir, which would be trivially ignorable).
        (wt / ".harness").mkdir(exist_ok=True)
        (wt / ".harness" / "WORKTREE_UNIT.json").write_text(
            json.dumps({"batch_id": batch_id, "unit_id": unit_id}), encoding="utf-8"
        )
        return f".harness/worktrees/{batch_id}/{unit_id}"

    def _fleet_entry(self, unit_id, batch_id=None, worktree_path=None, branch=None):
        batch_id = batch_id or self.batch_id
        return {
            "unit_id": unit_id,
            "phase_id": "PHASE_X",
            "worktree_path": worktree_path if worktree_path is not None else f".harness/worktrees/{batch_id}/{unit_id}",
            "branch": branch if branch is not None else f"harness/{batch_id}/{unit_id}",
            "status": "running",
            "started_at": "2026-04-20T02:30:00Z",
            "ended_at": None,
            "agent_summary_path": None,
            "conflict": None,
        }

    def test_on_disk_worktree_without_fleet_entry_is_orphan(self):
        # Create a worktree on disk but do NOT list it in state.fleet.
        self._worktree_dir(self.batch_id, "u_ghost")
        _write_state_with_fleet(self.temp_dir, self.batch_id, units=[])

        returncode, output = run_sync_harness(self.temp_dir)
        self.assertEqual(returncode, 0)

        orphans = [d for d in output["divergences"] if d.get("type") == "orphan_worktree"]
        self.assertEqual(len(orphans), 1)
        self.assertEqual(orphans[0]["batch_id"], self.batch_id)
        self.assertEqual(orphans[0]["unit_id"], "u_ghost")
        self.assertEqual(
            orphans[0]["worktree_path"],
            f".harness/worktrees/{self.batch_id}/u_ghost",
        )

    def test_fleet_entry_without_on_disk_worktree_is_stale(self):
        # Fleet lists a unit but no worktree dir exists.
        _write_state_with_fleet(
            self.temp_dir, self.batch_id,
            units=[self._fleet_entry("u_missing")],
        )

        returncode, output = run_sync_harness(self.temp_dir)
        self.assertEqual(returncode, 0)

        stale = [d for d in output["divergences"] if d.get("type") == "stale_fleet_entry"]
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["unit_id"], "u_missing")
        self.assertEqual(stale[0]["batch_id"], self.batch_id)
        self.assertEqual(
            stale[0]["worktree_path"],
            f".harness/worktrees/{self.batch_id}/u_missing",
        )
        self.assertEqual(stale[0]["branch"], f"harness/{self.batch_id}/u_missing")

    def test_harness_branch_without_fleet_entry_is_orphan(self):
        # Create a branch matching harness/batch_*/ with no matching fleet entry.
        orphan_branch = f"harness/{self.batch_id}/u_orphan_branch"
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "branch", orphan_branch],
            check=True,
        )
        _write_state_with_fleet(self.temp_dir, self.batch_id, units=[])

        returncode, output = run_sync_harness(self.temp_dir)
        self.assertEqual(returncode, 0)

        branch_orphans = [
            d for d in output["divergences"] if d.get("type") == "orphan_branch"
        ]
        # We might get a match for each harness branch present -- filter to ours.
        ours = [d for d in branch_orphans if d["branch"] == orphan_branch]
        self.assertEqual(len(ours), 1)
        self.assertEqual(ours[0]["batch_id"], self.batch_id)
        self.assertEqual(ours[0]["unit_id"], "u_orphan_branch")

    def test_clean_state_produces_no_fleet_divergences(self):
        # On-disk worktree + matching fleet entry + matching branch ->
        # zero fleet-drift divergences. (Non-fleet divergences may still
        # appear from existing phase-report logic and that's fine.)
        self._worktree_dir(self.batch_id, "u_ok")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "branch",
             f"harness/{self.batch_id}/u_ok"], check=True,
        )
        _write_state_with_fleet(
            self.temp_dir, self.batch_id, units=[self._fleet_entry("u_ok")],
        )

        returncode, output = run_sync_harness(self.temp_dir)
        self.assertEqual(returncode, 0)

        fleet_divergence_types = {"orphan_worktree", "stale_fleet_entry", "orphan_branch"}
        fleet_drift = [
            d for d in output["divergences"]
            if d.get("type") in fleet_divergence_types
        ]
        self.assertEqual(fleet_drift, [])

    def test_multiple_divergence_types_reported_together(self):
        # One of each: orphan worktree, stale fleet entry, orphan branch.
        self._worktree_dir(self.batch_id, "u_disk_only")                   # orphan worktree
        _write_state_with_fleet(
            self.temp_dir, self.batch_id,
            units=[self._fleet_entry("u_fleet_only")],                     # stale fleet entry
        )
        orphan_branch = f"harness/{self.batch_id}/u_branch_only"
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "branch", orphan_branch],
            check=True,
        )

        returncode, output = run_sync_harness(self.temp_dir)
        self.assertEqual(returncode, 0)

        by_type = {}
        for d in output["divergences"]:
            by_type.setdefault(d.get("type"), []).append(d)

        self.assertEqual(len(by_type.get("orphan_worktree", [])), 1)
        self.assertEqual(len(by_type.get("stale_fleet_entry", [])), 1)
        self.assertEqual(len(by_type.get("orphan_branch", [])), 1)

        self.assertEqual(by_type["orphan_worktree"][0]["unit_id"], "u_disk_only")
        self.assertEqual(by_type["stale_fleet_entry"][0]["unit_id"], "u_fleet_only")
        self.assertEqual(by_type["orphan_branch"][0]["unit_id"], "u_branch_only")


if __name__ == "__main__":
    unittest.main()
