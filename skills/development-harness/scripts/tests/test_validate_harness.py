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
from validate_harness import _find_cycle, _is_touches_path_safe

SCRIPT_DIR = Path(__file__).resolve().parent.parent
VALIDATE_SCRIPT = SCRIPT_DIR / "validate_harness.py"


def _unit(unit_id, depends_on=None, parallel_safe=False, touches_paths=None, status="pending"):
    """Build a v2-compliant unit dict for fixtures."""
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


class TestValidateHarnessV2Schema(unittest.TestCase):
    """Exercise the v2 required-field, path-safety, cycle, and fleet-mode rules."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))

    def _write_workspace(self, phase_graph=None, state=None, config=None, manifest=None):
        harness_dir = self.temp_dir / ".harness"
        harness_dir.mkdir()
        (harness_dir / "config.json").write_text(
            json.dumps(config or _valid_config(), indent=2), encoding="utf-8"
        )
        (harness_dir / "state.json").write_text(
            json.dumps(state or _valid_state(), indent=2), encoding="utf-8"
        )
        (harness_dir / "manifest.json").write_text(
            json.dumps(manifest or _valid_manifest(), indent=2), encoding="utf-8"
        )
        (harness_dir / "phase-graph.json").write_text(
            json.dumps(phase_graph or _valid_phase_graph(), indent=2), encoding="utf-8"
        )
        (harness_dir / "checkpoint.md").write_text("# Checkpoint\n", encoding="utf-8")
        (self.temp_dir / "PHASES").mkdir()
        return self.temp_dir

    def test_v1_phase_graph_rejected_with_recreate_pointer(self):
        """A v1 fixture must be rejected with an actionable re-create message."""
        v1_graph = {
            "schema_version": "1.0",
            "phases": [
                {"id": "PHASE_001", "slug": "p1", "status": "pending", "depends_on": [], "units": []}
            ],
        }
        root = self._write_workspace(phase_graph=v1_graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        self.assertFalse(output.get("valid"))
        joined = " ".join(output.get("errors", []))
        self.assertIn("/create-development-harness", joined)
        self.assertIn("phase-graph.json", joined)

    def test_v1_config_state_and_manifest_also_rejected(self):
        """All four JSON files gate on schema version."""
        v1 = lambda base: {**base, "schema_version": "1.0"}
        root = self._write_workspace(
            config=v1(_valid_config()),
            state=v1(_valid_state()),
            manifest=v1(_valid_manifest()),
            phase_graph=v1(_valid_phase_graph()),
        )
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        for name in ("config.json", "state.json", "manifest.json", "phase-graph.json"):
            self.assertIn(name, joined)
        self.assertIn("/create-development-harness", joined)

    def test_unit_missing_depends_on_rejected(self):
        graph = {
            "schema_version": SCHEMA_VERSION,
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": [],
                    "units": [
                        {
                            "id": "u1",
                            "description": "missing depends_on",
                            "status": "pending",
                            "parallel_safe": False,
                        }
                    ],
                }
            ],
        }
        root = self._write_workspace(phase_graph=graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("depends_on", joined)
        self.assertIn("missing", joined)

    def test_unit_missing_parallel_safe_rejected(self):
        graph = {
            "schema_version": SCHEMA_VERSION,
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": [],
                    "units": [
                        {
                            "id": "u1",
                            "description": "missing parallel_safe",
                            "status": "pending",
                            "depends_on": [],
                        }
                    ],
                }
            ],
        }
        root = self._write_workspace(phase_graph=graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("parallel_safe", joined)

    def test_parallel_safe_true_without_touches_paths_rejected(self):
        graph = {
            "schema_version": SCHEMA_VERSION,
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": [],
                    "units": [_unit("u1", parallel_safe=True)],
                }
            ],
        }
        root = self._write_workspace(phase_graph=graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("parallel_safe", joined)
        self.assertIn("touches_paths", joined)

    def test_parallel_safe_true_with_empty_touches_paths_rejected(self):
        graph = {
            "schema_version": SCHEMA_VERSION,
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": [],
                    "units": [_unit("u1", parallel_safe=True, touches_paths=[])],
                }
            ],
        }
        root = self._write_workspace(phase_graph=graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("touches_paths", joined)
        self.assertIn("non-empty", joined)

    def test_touches_paths_rejects_parent_traversal(self):
        graph = {
            "schema_version": SCHEMA_VERSION,
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": [],
                    "units": [_unit("u1", parallel_safe=True, touches_paths=["../secrets/**"])],
                }
            ],
        }
        root = self._write_workspace(phase_graph=graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("touches_paths", joined)
        self.assertIn("..", joined)

    def test_touches_paths_rejects_posix_absolute(self):
        graph = {
            "schema_version": SCHEMA_VERSION,
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": [],
                    "units": [_unit("u1", parallel_safe=True, touches_paths=["/etc/passwd"])],
                }
            ],
        }
        root = self._write_workspace(phase_graph=graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("touches_paths", joined)
        self.assertIn("unsafe", joined)

    def test_touches_paths_rejects_windows_absolute(self):
        graph = {
            "schema_version": SCHEMA_VERSION,
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": [],
                    "units": [_unit("u1", parallel_safe=True, touches_paths=["C:\\Windows\\System32"])],
                }
            ],
        }
        root = self._write_workspace(phase_graph=graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("touches_paths", joined)
        self.assertIn("unsafe", joined)

    def test_phase_depends_on_cycle_detected(self):
        graph = {
            "schema_version": SCHEMA_VERSION,
            "phases": [
                {
                    "id": "PHASE_A",
                    "slug": "a",
                    "status": "pending",
                    "depends_on": ["PHASE_B"],
                    "units": [],
                },
                {
                    "id": "PHASE_B",
                    "slug": "b",
                    "status": "pending",
                    "depends_on": ["PHASE_A"],
                    "units": [],
                },
            ],
        }
        root = self._write_workspace(phase_graph=graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("phase depends_on cycle", joined)
        self.assertIn("PHASE_A", joined)
        self.assertIn("PHASE_B", joined)

    def test_unit_depends_on_cycle_detected(self):
        graph = {
            "schema_version": SCHEMA_VERSION,
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": [],
                    "units": [
                        _unit("u1", depends_on=["u2"]),
                        _unit("u2", depends_on=["u1"]),
                    ],
                }
            ],
        }
        root = self._write_workspace(phase_graph=graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("unit depends_on cycle", joined)
        self.assertIn("u1", joined)
        self.assertIn("u2", joined)

    def test_unknown_phase_dependency_rejected(self):
        graph = {
            "schema_version": SCHEMA_VERSION,
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": ["PHASE_999"],
                    "units": [],
                }
            ],
        }
        root = self._write_workspace(phase_graph=graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("unknown phase", joined)
        self.assertIn("PHASE_999", joined)

    def test_unknown_unit_dependency_rejected(self):
        graph = {
            "schema_version": SCHEMA_VERSION,
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": [],
                    "units": [_unit("u1", depends_on=["ghost"])],
                }
            ],
        }
        root = self._write_workspace(phase_graph=graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("unknown unit", joined)
        self.assertIn("ghost", joined)

    def test_fleet_mode_invalid_enum_rejected(self):
        state = {
            "schema_version": SCHEMA_VERSION,
            "execution": {"fleet": {"mode": "galloping"}},
            "checkpoint": {},
        }
        root = self._write_workspace(state=state)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("fleet.mode", joined)
        self.assertIn("galloping", joined)

    def test_fleet_missing_mode_rejected(self):
        state = {
            "schema_version": SCHEMA_VERSION,
            "execution": {"fleet": {"batch_id": "b1"}},
            "checkpoint": {},
        }
        root = self._write_workspace(state=state)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 1)
        joined = " ".join(output.get("errors", []))
        self.assertIn("fleet.mode", joined)

    def test_fleet_mode_idle_accepted(self):
        state = {
            "schema_version": SCHEMA_VERSION,
            "execution": {"fleet": {"mode": "idle"}},
            "checkpoint": {},
        }
        root = self._write_workspace(state=state)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 0)
        self.assertTrue(output.get("valid"))

    def test_valid_v2_unit_accepted(self):
        graph = {
            "schema_version": SCHEMA_VERSION,
            "phases": [
                {
                    "id": "PHASE_001",
                    "slug": "p1",
                    "status": "pending",
                    "depends_on": [],
                    "units": [
                        _unit("u1", parallel_safe=False),
                        _unit("u2", depends_on=["u1"], parallel_safe=True, touches_paths=["src/**"]),
                    ],
                }
            ],
        }
        root = self._write_workspace(phase_graph=graph)
        returncode, output = run_validate_harness(root)
        self.assertEqual(returncode, 0, f"Expected valid, got errors: {output.get('errors')}")
        self.assertTrue(output.get("valid"))


class TestPathSafetyHelper(unittest.TestCase):
    """Direct coverage for _is_touches_path_safe edge cases."""

    def test_accepts_repo_relative_glob(self):
        self.assertTrue(_is_touches_path_safe("src/foo/**"))
        self.assertTrue(_is_touches_path_safe("src/foo/bar.ts"))
        self.assertTrue(_is_touches_path_safe("a/b/c"))

    def test_rejects_parent_traversal(self):
        self.assertFalse(_is_touches_path_safe("../foo"))
        self.assertFalse(_is_touches_path_safe("src/../etc"))
        self.assertFalse(_is_touches_path_safe("..\\foo"))

    def test_rejects_absolute_paths(self):
        self.assertFalse(_is_touches_path_safe("/etc/passwd"))
        self.assertFalse(_is_touches_path_safe("C:/Windows"))
        self.assertFalse(_is_touches_path_safe("C:\\Windows"))
        self.assertFalse(_is_touches_path_safe("D:/data"))

    def test_rejects_non_string_and_empty(self):
        self.assertFalse(_is_touches_path_safe(""))
        self.assertFalse(_is_touches_path_safe(None))
        self.assertFalse(_is_touches_path_safe(123))
        self.assertFalse(_is_touches_path_safe(["a"]))


class TestFindCycleHelper(unittest.TestCase):
    """Direct coverage for _find_cycle."""

    def test_linear_is_acyclic(self):
        graph = {"a": ["b"], "b": ["c"], "c": []}
        self.assertIsNone(_find_cycle(graph))

    def test_self_loop_detected(self):
        graph = {"a": ["a"]}
        cycle = _find_cycle(graph)
        self.assertIsNotNone(cycle)
        self.assertIn("a", cycle)

    def test_two_cycle_detected(self):
        graph = {"a": ["b"], "b": ["a"]}
        cycle = _find_cycle(graph)
        self.assertIsNotNone(cycle)
        self.assertIn("a", cycle)
        self.assertIn("b", cycle)

    def test_three_cycle_detected(self):
        graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
        cycle = _find_cycle(graph)
        self.assertIsNotNone(cycle)
        self.assertEqual(cycle[0], cycle[-1])
        self.assertEqual(set(cycle), {"a", "b", "c"})

    def test_diamond_is_acyclic(self):
        graph = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        self.assertIsNone(_find_cycle(graph))

    def test_unknown_dep_ignored_for_cycle(self):
        # Referential integrity is checked separately; cycle detection
        # must not walk into undeclared nodes.
        graph = {"a": ["ghost"]}
        self.assertIsNone(_find_cycle(graph))


if __name__ == "__main__":
    unittest.main()
