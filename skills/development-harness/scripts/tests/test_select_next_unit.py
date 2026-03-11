"""Tests for select_next_unit.py via subprocess."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
SELECT_SCRIPT = SCRIPT_DIR / "select_next_unit.py"


def run_select_next_unit(root, phase_graph_path):
    """Run select_next_unit.py and return parsed JSON from stdout."""
    result = subprocess.run(
        [
            sys.executable,
            str(SELECT_SCRIPT),
            "--root",
            str(root),
            "--phase-graph",
            str(phase_graph_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(SCRIPT_DIR),
    )
    result.check_returncode()
    return json.loads(result.stdout)


class TestSelectNextUnit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))

        # Ensure root has .harness so find_harness_root would work if needed
        (self.temp_dir / ".harness").mkdir(exist_ok=True)

        # simple_graph.json: 1 phase, 3 units (first completed, second in_progress, third pending)
        simple_graph = {
            "schema_version": "1.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "phase-one",
                    "status": "in_progress",
                    "depends_on": [],
                    "units": [
                        {"id": "UNIT_001", "description": "First", "status": "completed"},
                        {"id": "UNIT_002", "description": "Second", "status": "in_progress"},
                        {"id": "UNIT_003", "description": "Third", "status": "pending"},
                    ],
                }
            ],
        }
        (self.temp_dir / "simple_graph.json").write_text(
            json.dumps(simple_graph, indent=2),
            encoding="utf-8",
        )
        self.simple_graph = self.temp_dir / "simple_graph.json"

        # no_in_progress_graph.json: no in_progress unit, returns first pending
        no_in_progress_graph = {
            "schema_version": "1.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "phase-one",
                    "status": "in_progress",
                    "depends_on": [],
                    "units": [
                        {"id": "UNIT_001", "description": "First", "status": "completed"},
                        {"id": "UNIT_002", "description": "Second", "status": "pending"},
                        {"id": "UNIT_003", "description": "Third", "status": "pending"},
                    ],
                }
            ],
        }
        (self.temp_dir / "no_in_progress_graph.json").write_text(
            json.dumps(no_in_progress_graph, indent=2),
            encoding="utf-8",
        )
        self.no_in_progress_graph = self.temp_dir / "no_in_progress_graph.json"

        # dependency_graph.json: PHASE_002 depends on PHASE_001, PHASE_001 completed
        dependency_graph = {
            "schema_version": "1.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "phase-one",
                    "status": "completed",
                    "depends_on": [],
                    "units": [
                        {"id": "UNIT_001", "description": "Done", "status": "completed"},
                    ],
                },
                {
                    "id": "PHASE_002",
                    "slug": "phase-two",
                    "status": "pending",
                    "depends_on": ["PHASE_001"],
                    "units": [
                        {"id": "UNIT_002", "description": "Next", "status": "pending"},
                    ],
                },
            ],
        }
        (self.temp_dir / "dependency_graph.json").write_text(
            json.dumps(dependency_graph, indent=2),
            encoding="utf-8",
        )
        self.dependency_graph = self.temp_dir / "dependency_graph.json"

        # all_complete.json: all phases and units completed
        all_complete = {
            "schema_version": "1.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "phase-one",
                    "status": "completed",
                    "depends_on": [],
                    "units": [
                        {"id": "UNIT_001", "description": "Done", "status": "completed"},
                    ],
                },
            ],
        }
        (self.temp_dir / "all_complete.json").write_text(
            json.dumps(all_complete, indent=2),
            encoding="utf-8",
        )
        self.all_complete = self.temp_dir / "all_complete.json"

        # blocked_graph.json: PHASE_002 depends on incomplete PHASE_001
        blocked_graph = {
            "schema_version": "1.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "phase-one",
                    "status": "in_progress",
                    "depends_on": [],
                    "units": [
                        {"id": "UNIT_001", "description": "In progress", "status": "in_progress"},
                    ],
                },
                {
                    "id": "PHASE_002",
                    "slug": "phase-two",
                    "status": "pending",
                    "depends_on": ["PHASE_001"],
                    "units": [
                        {"id": "UNIT_002", "description": "Blocked", "status": "pending"},
                    ],
                },
            ],
        }
        (self.temp_dir / "blocked_graph.json").write_text(
            json.dumps(blocked_graph, indent=2),
            encoding="utf-8",
        )
        self.blocked_graph = self.temp_dir / "blocked_graph.json"

    def test_returns_in_progress_unit(self):
        result = run_select_next_unit(self.temp_dir, self.simple_graph)
        self.assertTrue(result["found"])
        self.assertEqual(result["unit_id"], "UNIT_002")
        self.assertEqual(result["unit_description"], "Second")
        self.assertFalse(result["all_complete"])

    def test_returns_first_pending_if_no_in_progress(self):
        result = run_select_next_unit(self.temp_dir, self.no_in_progress_graph)
        self.assertTrue(result["found"])
        self.assertEqual(result["unit_id"], "UNIT_002")
        self.assertEqual(result["unit_description"], "Second")

    def test_respects_dependencies(self):
        result = run_select_next_unit(self.temp_dir, self.dependency_graph)
        self.assertTrue(result["found"])
        self.assertEqual(result["phase_id"], "PHASE_002")
        self.assertEqual(result["unit_id"], "UNIT_002")

    def test_blocked_phase_skipped(self):
        result = run_select_next_unit(self.temp_dir, self.blocked_graph)
        self.assertTrue(result["found"])
        self.assertEqual(result["phase_id"], "PHASE_001")
        self.assertEqual(result["unit_id"], "UNIT_001")
        self.assertNotEqual(result["phase_id"], "PHASE_002")

    def test_all_complete_returns_not_found(self):
        result = run_select_next_unit(self.temp_dir, self.all_complete)
        self.assertFalse(result["found"])
        self.assertTrue(result["all_complete"])
        self.assertIsNone(result["unit_id"])


if __name__ == "__main__":
    unittest.main()
