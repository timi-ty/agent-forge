"""Tests for select_next_unit.py via subprocess."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SCRIPT_DIR = Path(__file__).resolve().parent.parent
SELECT_SCRIPT = SCRIPT_DIR / "select_next_unit.py"


def run_select_next_unit(root, phase_graph_path, extra_args=None):
    """Run select_next_unit.py and return (returncode, stdout_json, stderr)."""
    cmd = [
        sys.executable,
        str(SELECT_SCRIPT),
        "--root",
        str(root),
        "--phase-graph",
        str(phase_graph_path),
    ]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPT_DIR))
    try:
        parsed = json.loads(result.stdout) if result.stdout else None
    except json.JSONDecodeError:
        parsed = None
    return result.returncode, parsed, result.stderr


def _unit(unit_id, status="pending", depends_on=None, parallel_safe=False, touches_paths=None):
    unit = {
        "id": unit_id,
        "description": f"{unit_id} description",
        "status": status,
        "depends_on": list(depends_on) if depends_on else [],
        "parallel_safe": parallel_safe,
    }
    if touches_paths is not None:
        unit["touches_paths"] = list(touches_paths)
    return unit


class TestSelectNextUnit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))
        (self.temp_dir / ".harness").mkdir(exist_ok=True)

        simple_graph = {
            "schema_version": "2.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "phase-one",
                    "status": "in_progress",
                    "depends_on": [],
                    "units": [
                        _unit("UNIT_001", status="completed"),
                        _unit("UNIT_002", status="in_progress", depends_on=["UNIT_001"]),
                        _unit("UNIT_003", depends_on=["UNIT_002"]),
                    ],
                }
            ],
        }
        self.simple_graph = self._write("simple_graph.json", simple_graph)

        no_in_progress_graph = {
            "schema_version": "2.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "phase-one",
                    "status": "in_progress",
                    "depends_on": [],
                    "units": [
                        _unit("UNIT_001", status="completed"),
                        _unit("UNIT_002", depends_on=["UNIT_001"]),
                        _unit("UNIT_003", depends_on=["UNIT_002"]),
                    ],
                }
            ],
        }
        self.no_in_progress_graph = self._write(
            "no_in_progress_graph.json", no_in_progress_graph
        )

        dependency_graph = {
            "schema_version": "2.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "phase-one",
                    "status": "completed",
                    "depends_on": [],
                    "units": [_unit("UNIT_001", status="completed")],
                },
                {
                    "id": "PHASE_002",
                    "slug": "phase-two",
                    "status": "pending",
                    "depends_on": ["PHASE_001"],
                    "units": [_unit("UNIT_002")],
                },
            ],
        }
        self.dependency_graph = self._write("dependency_graph.json", dependency_graph)

        all_complete = {
            "schema_version": "2.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "phase-one",
                    "status": "completed",
                    "depends_on": [],
                    "units": [_unit("UNIT_001", status="completed")],
                }
            ],
        }
        self.all_complete = self._write("all_complete.json", all_complete)

        blocked_graph = {
            "schema_version": "2.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "phase-one",
                    "status": "in_progress",
                    "depends_on": [],
                    "units": [_unit("UNIT_001", status="in_progress")],
                },
                {
                    "id": "PHASE_002",
                    "slug": "phase-two",
                    "status": "pending",
                    "depends_on": ["PHASE_001"],
                    "units": [_unit("UNIT_002")],
                },
            ],
        }
        self.blocked_graph = self._write("blocked_graph.json", blocked_graph)

    def _write(self, name, data):
        path = self.temp_dir / name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def test_returns_in_progress_unit(self):
        rc, result, _ = run_select_next_unit(self.temp_dir, self.simple_graph)
        self.assertEqual(rc, 0)
        self.assertTrue(result["found"])
        self.assertEqual(result["unit_id"], "UNIT_002")
        self.assertEqual(result["unit_description"], "UNIT_002 description")
        self.assertFalse(result["all_complete"])

    def test_returns_first_pending_if_no_in_progress(self):
        rc, result, _ = run_select_next_unit(self.temp_dir, self.no_in_progress_graph)
        self.assertEqual(rc, 0)
        self.assertTrue(result["found"])
        self.assertEqual(result["unit_id"], "UNIT_002")

    def test_respects_dependencies(self):
        rc, result, _ = run_select_next_unit(self.temp_dir, self.dependency_graph)
        self.assertEqual(rc, 0)
        self.assertTrue(result["found"])
        self.assertEqual(result["phase_id"], "PHASE_002")
        self.assertEqual(result["unit_id"], "UNIT_002")

    def test_blocked_phase_skipped(self):
        rc, result, _ = run_select_next_unit(self.temp_dir, self.blocked_graph)
        self.assertEqual(rc, 0)
        self.assertTrue(result["found"])
        self.assertEqual(result["phase_id"], "PHASE_001")
        self.assertEqual(result["unit_id"], "UNIT_001")

    def test_all_complete_returns_not_found(self):
        rc, result, _ = run_select_next_unit(self.temp_dir, self.all_complete)
        self.assertEqual(rc, 0)
        self.assertFalse(result["found"])
        self.assertTrue(result["all_complete"])
        self.assertIsNone(result["unit_id"])


class TestFrontierFlag(unittest.TestCase):
    """--frontier returns an array of every ready unit; --max truncates it."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))
        (self.temp_dir / ".harness").mkdir(exist_ok=True)

    def _write(self, name, data):
        path = self.temp_dir / name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def test_frontier_returns_all_ready_units(self):
        graph = {
            "schema_version": "2.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "in_progress",
                    "depends_on": [],
                    "units": [
                        _unit("u1", status="completed"),
                        _unit("u2", depends_on=["u1"]),
                        _unit("u3", depends_on=["u1"]),
                        _unit("u4", depends_on=["u2", "u3"]),
                    ],
                }
            ],
        }
        path = self._write("frontier.json", graph)
        rc, result, _ = run_select_next_unit(self.temp_dir, path, ["--frontier"])
        self.assertEqual(rc, 0)
        self.assertIsInstance(result, list)
        ids = [u["id"] for u in result]
        # u1 is completed; u4 is blocked on u2 & u3; u2 and u3 are ready.
        self.assertEqual(ids, ["u2", "u3"])

    def test_frontier_max_caps_the_list(self):
        graph = {
            "schema_version": "2.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "in_progress",
                    "depends_on": [],
                    "units": [
                        _unit("u1"),
                        _unit("u2"),
                        _unit("u3"),
                        _unit("u4"),
                    ],
                }
            ],
        }
        path = self._write("cap.json", graph)
        rc, result, _ = run_select_next_unit(
            self.temp_dir, path, ["--frontier", "--max", "2"]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(len(result), 2)
        self.assertEqual([u["id"] for u in result], ["u1", "u2"])

    def test_frontier_preserves_v2_unit_fields(self):
        graph = {
            "schema_version": "2.0",
            "phases": [
                {
                    "id": "PHASE_X",
                    "slug": "x",
                    "status": "in_progress",
                    "depends_on": [],
                    "units": [
                        _unit(
                            "u1",
                            parallel_safe=True,
                            touches_paths=["src/**"],
                        ),
                    ],
                }
            ],
        }
        path = self._write("pass_through.json", graph)
        rc, result, _ = run_select_next_unit(self.temp_dir, path, ["--frontier"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertEqual(entry["phase_id"], "PHASE_X")
        self.assertEqual(entry["phase_slug"], "x")
        self.assertTrue(entry["parallel_safe"])
        self.assertEqual(entry["touches_paths"], ["src/**"])
        self.assertEqual(entry["depends_on"], [])

    def test_frontier_empty_when_all_complete(self):
        graph = {
            "schema_version": "2.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "completed",
                    "depends_on": [],
                    "units": [_unit("u1", status="completed")],
                }
            ],
        }
        path = self._write("done.json", graph)
        rc, result, _ = run_select_next_unit(self.temp_dir, path, ["--frontier"])
        self.assertEqual(rc, 0)
        self.assertEqual(result, [])


class TestNoLegacyFallback(unittest.TestCase):
    """Malformed units must raise a clear error rather than fall back to list order."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))
        (self.temp_dir / ".harness").mkdir(exist_ok=True)

    def _write(self, name, data):
        path = self.temp_dir / name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def test_unit_missing_depends_on_errors(self):
        graph = {
            "schema_version": "2.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": [],
                    "units": [
                        {
                            "id": "u1",
                            "description": "no depends_on",
                            "status": "pending",
                            "parallel_safe": False,
                        }
                    ],
                }
            ],
        }
        path = self._write("malformed.json", graph)
        rc, _result, stderr = run_select_next_unit(
            self.temp_dir, path, ["--frontier"]
        )
        self.assertEqual(rc, 2)
        self.assertIn("depends_on", stderr)
        self.assertIn("validate_harness", stderr)

    def test_unit_with_non_list_depends_on_errors(self):
        graph = {
            "schema_version": "2.0",
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": [],
                    "units": [
                        {
                            "id": "u1",
                            "description": "bad depends_on",
                            "status": "pending",
                            "parallel_safe": False,
                            "depends_on": "not-a-list",
                        }
                    ],
                }
            ],
        }
        path = self._write("bad_type.json", graph)
        rc, _result, stderr = run_select_next_unit(self.temp_dir, path, ["--frontier"])
        self.assertEqual(rc, 2)
        self.assertIn("depends_on", stderr)


if __name__ == "__main__":
    unittest.main()
