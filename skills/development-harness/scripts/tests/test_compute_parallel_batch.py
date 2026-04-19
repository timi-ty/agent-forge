"""Tests for compute_parallel_batch.py -- unit 009 scope (structural coverage).

Unit 010 adds one dedicated test per exclusion reason. This file covers the
core algorithm: packing, capacity, overlap, cross-phase deferral, batch_id
format, and the two helpers (_patterns_overlap, _parallelism_config).
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compute_parallel_batch import (  # noqa: E402
    _is_literal,
    _literal_prefix,
    _make_batch_id,
    _parallelism_config,
    _patterns_overlap,
    compute_batch,
)

SCRIPT_DIR = Path(__file__).resolve().parent.parent
BATCH_SCRIPT = SCRIPT_DIR / "compute_parallel_batch.py"


def _unit(unit_id, parallel_safe=True, touches_paths=None, phase_id="PHASE_X"):
    return {
        "phase_id": phase_id,
        "phase_slug": phase_id.lower(),
        "id": unit_id,
        "description": f"{unit_id} description",
        "status": "pending",
        "depends_on": [],
        "parallel_safe": parallel_safe,
        "touches_paths": list(touches_paths) if touches_paths else [],
    }


def _default_parallelism(**overrides):
    base = {
        "enabled": True,
        "max_concurrent_units": 3,
        "conflict_strategy": "abort_batch",
        "require_touches_paths": True,
        "allow_cross_phase": False,
    }
    base.update(overrides)
    return base


class TestPatternOverlap(unittest.TestCase):
    def test_two_identical_literals_overlap(self):
        self.assertTrue(_patterns_overlap("src/auth.ts", "src/auth.ts"))

    def test_two_distinct_literals_do_not_overlap(self):
        self.assertFalse(_patterns_overlap("src/auth.ts", "src/users.ts"))

    def test_literal_matches_glob(self):
        self.assertTrue(_patterns_overlap("src/auth/login.ts", "src/auth/*.ts"))
        self.assertTrue(_patterns_overlap("src/auth/login.ts", "src/auth/**"))
        self.assertFalse(_patterns_overlap("src/auth/login.ts", "tests/**"))

    def test_glob_containing_another_glob_overlaps(self):
        self.assertTrue(_patterns_overlap("src/**", "src/auth/**"))
        self.assertTrue(_patterns_overlap("src/auth/**", "src/**"))

    def test_disjoint_globs_do_not_overlap(self):
        self.assertFalse(_patterns_overlap("src/auth/**", "src/users/**"))

    def test_empty_prefix_star_overlaps_everything(self):
        self.assertTrue(_patterns_overlap("**", "src/auth/**"))

    def test_is_literal_and_prefix_helpers(self):
        self.assertTrue(_is_literal("src/auth.ts"))
        self.assertFalse(_is_literal("src/*.ts"))
        self.assertFalse(_is_literal("src/a?.ts"))
        self.assertFalse(_is_literal("src/[a-z].ts"))
        self.assertEqual(_literal_prefix("src/auth/*.ts"), "src/auth/")
        self.assertEqual(_literal_prefix("src/auth/login.ts"), "src/auth/login.ts")
        self.assertEqual(_literal_prefix("**/foo"), "")


class TestParallelismConfigExtraction(unittest.TestCase):
    def test_string_execution_mode_falls_back_to_defaults(self):
        # A v1-style config ("execution_mode": "local") should not crash.
        cfg = _parallelism_config({"execution_mode": "local"})
        self.assertFalse(cfg["enabled"])
        self.assertEqual(cfg["max_concurrent_units"], 3)
        self.assertTrue(cfg["require_touches_paths"])

    def test_object_execution_mode_is_honoured(self):
        cfg = _parallelism_config(
            {
                "execution_mode": {
                    "parallelism": {
                        "enabled": True,
                        "max_concurrent_units": 5,
                        "conflict_strategy": "serialize_conflicted",
                        "require_touches_paths": False,
                        "allow_cross_phase": True,
                    }
                }
            }
        )
        self.assertTrue(cfg["enabled"])
        self.assertEqual(cfg["max_concurrent_units"], 5)
        self.assertEqual(cfg["conflict_strategy"], "serialize_conflicted")
        self.assertFalse(cfg["require_touches_paths"])
        self.assertTrue(cfg["allow_cross_phase"])

    def test_missing_parallelism_uses_defaults(self):
        cfg = _parallelism_config({"execution_mode": {}})
        self.assertFalse(cfg["enabled"])
        self.assertEqual(cfg["max_concurrent_units"], 3)


class TestComputeBatch(unittest.TestCase):
    def test_empty_frontier_empty_batch(self):
        result = compute_batch([], _default_parallelism())
        self.assertEqual(result["batch"], [])
        self.assertEqual(result["excluded"], [])
        self.assertTrue(result["batch_id"].startswith("batch_"))

    def test_non_overlapping_units_all_fit_under_capacity(self):
        frontier = [
            _unit("u1", touches_paths=["src/auth/**"]),
            _unit("u2", touches_paths=["src/users/**"]),
            _unit("u3", touches_paths=["src/posts/**"]),
        ]
        result = compute_batch(frontier, _default_parallelism(max_concurrent_units=3))
        self.assertEqual([u["id"] for u in result["batch"]], ["u1", "u2", "u3"])
        self.assertEqual(result["excluded"], [])

    def test_capacity_caps_the_batch(self):
        frontier = [
            _unit("u1", touches_paths=["a/**"]),
            _unit("u2", touches_paths=["b/**"]),
            _unit("u3", touches_paths=["c/**"]),
            _unit("u4", touches_paths=["d/**"]),
            _unit("u5", touches_paths=["e/**"]),
        ]
        result = compute_batch(frontier, _default_parallelism(max_concurrent_units=3))
        self.assertEqual([u["id"] for u in result["batch"]], ["u1", "u2", "u3"])
        self.assertEqual(
            result["excluded"],
            [
                {"unit_id": "u4", "reason": "capacity_cap"},
                {"unit_id": "u5", "reason": "capacity_cap"},
            ],
        )

    def test_overlap_pairs_serialize_first_wins(self):
        frontier = [
            _unit("u1", touches_paths=["src/shared/**"]),
            _unit("u2", touches_paths=["src/shared/auth.ts"]),
            _unit("u3", touches_paths=["src/users/**"]),
        ]
        result = compute_batch(frontier, _default_parallelism(max_concurrent_units=3))
        batch_ids = [u["id"] for u in result["batch"]]
        self.assertEqual(batch_ids, ["u1", "u3"])
        self.assertEqual(
            result["excluded"],
            [{"unit_id": "u2", "reason": "path_overlap_with:u1"}],
        )

    def test_parallel_safe_false_excluded(self):
        frontier = [
            _unit("u1", parallel_safe=False, touches_paths=[]),
            _unit("u2", touches_paths=["src/**"]),
        ]
        result = compute_batch(frontier, _default_parallelism())
        self.assertEqual([u["id"] for u in result["batch"]], ["u2"])
        self.assertEqual(
            result["excluded"],
            [{"unit_id": "u1", "reason": "not_parallel_safe"}],
        )

    def test_require_touches_paths_excludes_empty(self):
        frontier = [
            _unit("u1", touches_paths=[]),
            _unit("u2", touches_paths=["src/**"]),
        ]
        result = compute_batch(frontier, _default_parallelism(require_touches_paths=True))
        self.assertEqual([u["id"] for u in result["batch"]], ["u2"])
        self.assertEqual(
            result["excluded"],
            [{"unit_id": "u1", "reason": "not_parallel_safe"}],
        )

    def test_require_touches_paths_false_allows_empty(self):
        frontier = [
            _unit("u1", touches_paths=[]),
            _unit("u2", touches_paths=["src/**"]),
        ]
        result = compute_batch(
            frontier, _default_parallelism(require_touches_paths=False)
        )
        # u1 is accepted (its "empty" touches_paths never overlap with u2).
        self.assertEqual([u["id"] for u in result["batch"]], ["u1", "u2"])

    def test_cross_phase_deferred_not_excluded(self):
        frontier = [
            _unit("a1", phase_id="PHASE_A", touches_paths=["src/a/**"]),
            _unit("b1", phase_id="PHASE_B", touches_paths=["src/b/**"]),
        ]
        result = compute_batch(frontier, _default_parallelism(allow_cross_phase=False))
        # b1 is deferred, not excluded (it remains eligible in a later batch).
        self.assertEqual([u["id"] for u in result["batch"]], ["a1"])
        self.assertEqual(result["excluded"], [])

    def test_cross_phase_allowed_when_flag_true(self):
        frontier = [
            _unit("a1", phase_id="PHASE_A", touches_paths=["src/a/**"]),
            _unit("b1", phase_id="PHASE_B", touches_paths=["src/b/**"]),
        ]
        result = compute_batch(frontier, _default_parallelism(allow_cross_phase=True))
        self.assertEqual([u["id"] for u in result["batch"]], ["a1", "b1"])


class TestBatchIdFormat(unittest.TestCase):
    def test_batch_id_is_utc_timestamped(self):
        fixed = datetime(2026, 4, 19, 20, 30, 0, tzinfo=timezone.utc)
        self.assertEqual(_make_batch_id(fixed), "batch_2026-04-19T20-30-00Z")

    def test_batch_id_auto_format_matches_spec(self):
        batch_id = _make_batch_id()
        self.assertRegex(batch_id, r"^batch_\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$")


class TestCliSmoke(unittest.TestCase):
    """End-to-end: --input and --config flags produce the same structured output."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))

    def _write(self, name, data):
        path = self.temp_dir / name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def test_cli_produces_structured_output(self):
        frontier_path = self._write(
            "frontier.json",
            [
                _unit("u1", touches_paths=["src/auth/**"]),
                _unit("u2", touches_paths=["src/users/**"]),
            ],
        )
        config_path = self._write(
            "config.json",
            {
                "schema_version": "2.0",
                "execution_mode": {
                    "parallelism": {
                        "enabled": True,
                        "max_concurrent_units": 3,
                        "conflict_strategy": "abort_batch",
                        "require_touches_paths": True,
                        "allow_cross_phase": False,
                    }
                },
            },
        )
        result = subprocess.run(
            [
                sys.executable,
                str(BATCH_SCRIPT),
                "--input",
                str(frontier_path),
                "--config",
                str(config_path),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertIn("batch_id", data)
        self.assertIn("batch", data)
        self.assertIn("excluded", data)
        self.assertEqual([u["id"] for u in data["batch"]], ["u1", "u2"])
        self.assertEqual(data["excluded"], [])
        self.assertRegex(
            data["batch_id"], r"^batch_\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$"
        )

    def test_cli_help_runs(self):
        result = subprocess.run(
            [sys.executable, str(BATCH_SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--input", result.stdout)
        self.assertIn("--config", result.stdout)


if __name__ == "__main__":
    unittest.main()
