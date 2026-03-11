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


if __name__ == "__main__":
    unittest.main()
