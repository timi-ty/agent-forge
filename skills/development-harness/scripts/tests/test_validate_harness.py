"""Tests for validate_harness.py via subprocess."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent dir so we can import from scripts if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness_utils import SCHEMA_VERSION

SCRIPT_DIR = Path(__file__).resolve().parent.parent
VALIDATE_SCRIPT = SCRIPT_DIR / "validate_harness.py"


def run_validate_harness(root):
    """Run validate_harness.py and return (returncode, parsed JSON from stdout)."""
    result = subprocess.run(
        [sys.executable, str(VALIDATE_SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        cwd=str(SCRIPT_DIR),
    )
    try:
        output = json.loads(result.stdout) if result.stdout else {}
    except json.JSONDecodeError:
        output = {}
    return result.returncode, output


def _valid_config():
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {"name": "test", "description": ""},
        "stack": {},
        "deployment": {},
        "git": {},
        "testing": {},
        "quality": {},
    }


def _valid_state():
    return {
        "schema_version": SCHEMA_VERSION,
        "execution": {},
        "checkpoint": {},
    }


def _valid_manifest():
    return {
        "schema_version": SCHEMA_VERSION,
        "entries": [
            {"path": "PHASES/", "ownership": "harness-owned", "type": "directory", "removable": True},
        ],
    }


def _valid_phase_graph():
    return {
        "schema_version": SCHEMA_VERSION,
        "phases": [
            {
                "id": "PHASE_001",
                "slug": "test",
                "status": "pending",
                "depends_on": [],
                "units": [],
            },
        ],
    }


class TestValidateHarness(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))

    def _create_valid_workspace(self):
        """Create valid_workspace: .harness/ with all required files + PHASES/."""
        harness_dir = self.temp_dir / ".harness"
        harness_dir.mkdir()
        (harness_dir / "config.json").write_text(json.dumps(_valid_config(), indent=2), encoding="utf-8")
        (harness_dir / "state.json").write_text(json.dumps(_valid_state(), indent=2), encoding="utf-8")
        (harness_dir / "manifest.json").write_text(json.dumps(_valid_manifest(), indent=2), encoding="utf-8")
        (harness_dir / "phase-graph.json").write_text(json.dumps(_valid_phase_graph(), indent=2), encoding="utf-8")
        (harness_dir / "checkpoint.md").write_text("# Checkpoint\n", encoding="utf-8")
        (self.temp_dir / "PHASES").mkdir()
        return self.temp_dir

    def _create_missing_file_workspace(self):
        """Create missing_file_workspace: .harness/ but missing state.json."""
        harness_dir = self.temp_dir / ".harness"
        harness_dir.mkdir()
        (harness_dir / "config.json").write_text(json.dumps(_valid_config(), indent=2), encoding="utf-8")
        # Intentionally omit state.json
        (harness_dir / "manifest.json").write_text(json.dumps(_valid_manifest(), indent=2), encoding="utf-8")
        (harness_dir / "phase-graph.json").write_text(json.dumps(_valid_phase_graph(), indent=2), encoding="utf-8")
        (harness_dir / "checkpoint.md").write_text("# Checkpoint\n", encoding="utf-8")
        (self.temp_dir / "PHASES").mkdir()
        return self.temp_dir

    def _create_invalid_json_workspace(self):
        """Create invalid_json_workspace: .harness/ with corrupt config.json."""
        harness_dir = self.temp_dir / ".harness"
        harness_dir.mkdir()
        (harness_dir / "config.json").write_text("{ invalid json }", encoding="utf-8")
        (harness_dir / "state.json").write_text(json.dumps(_valid_state(), indent=2), encoding="utf-8")
        (harness_dir / "manifest.json").write_text(json.dumps(_valid_manifest(), indent=2), encoding="utf-8")
        (harness_dir / "phase-graph.json").write_text(json.dumps(_valid_phase_graph(), indent=2), encoding="utf-8")
        (harness_dir / "checkpoint.md").write_text("# Checkpoint\n", encoding="utf-8")
        (self.temp_dir / "PHASES").mkdir()
        return self.temp_dir

    def test_valid_workspace_passes(self):
        root = self._create_valid_workspace()
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 0)
        self.assertTrue(output.get("valid"), f"Expected valid: true, got: {output}")

    def test_missing_required_file_fails(self):
        root = self._create_missing_file_workspace()
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        self.assertFalse(output.get("valid"), f"Expected valid: false, got: {output}")

    def test_invalid_json_fails(self):
        root = self._create_invalid_json_workspace()
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        self.assertFalse(output.get("valid"))
        errors = output.get("errors", [])
        error_str = " ".join(errors).lower()
        self.assertTrue(
            "config.json" in error_str or "invalid json" in error_str or "json" in error_str,
            f"Errors should mention corrupt file; got: {errors}",
        )


if __name__ == "__main__":
    unittest.main()
