"""Tests for dispatch_batch.py -- unit 019 scope.

Every test builds a throwaway git repo in a temp dir because the
script shells out to ``git worktree``. Configuration is kept minimal
(init + user config + one commit) so the suite stays fast enough for
CI and local iteration.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dispatch_batch import (  # noqa: E402
    DispatchError,
    _branch_name,
    _worktree_relpath,
    dispatch_batch,
)

SCRIPT_DIR = Path(__file__).resolve().parent.parent
DISPATCH_SCRIPT = SCRIPT_DIR / "dispatch_batch.py"


def _init_repo(root):
    """Initialize a minimal git repo with one commit suitable for worktrees."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "harness@test.local"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Harness Test"],
        check=True,
    )
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "initial commit"],
        check=True,
    )


def _unit(unit_id, phase_id="PHASE_X", touches_paths=None):
    return {
        "phase_id": phase_id,
        "id": unit_id,
        "touches_paths": list(touches_paths) if touches_paths else [],
    }


def _batch_result(batch_id, units):
    return {"batch_id": batch_id, "batch": list(units), "excluded": []}


class DispatchBatchTestBase(unittest.TestCase):
    """Shared fixture: a fresh git repo per test under a temp dir."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        # Normalise for assertions that compare paths via str().
        self.temp_dir = self.temp_dir.resolve()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))
        _init_repo(self.temp_dir)
        self.batch_id = "batch_2026-04-20T00-30-00Z"

    def _git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.temp_dir), *args],
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    def _branch_exists(self, branch):
        result = subprocess.run(
            ["git", "-C", str(self.temp_dir), "show-ref", "--verify", f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0


class TestHappyPath(DispatchBatchTestBase):
    def test_dispatch_creates_worktrees_and_branches(self):
        batch = _batch_result(
            self.batch_id,
            [
                _unit("unit_a", touches_paths=["src/a/**"]),
                _unit("unit_b", touches_paths=["src/b/**"]),
            ],
        )
        result = dispatch_batch(batch, root=self.temp_dir, now="2026-04-20T00:30:00Z")

        self.assertEqual(result["batch_id"], self.batch_id)
        self.assertEqual(result["fleet"]["mode"], "dispatched")
        self.assertEqual(len(result["fleet"]["units"]), 2)

        for unit_id in ("unit_a", "unit_b"):
            wt = self.temp_dir / _worktree_relpath(self.batch_id, unit_id)
            self.assertTrue(wt.is_dir(), f"worktree missing: {wt}")
            self.assertTrue(self._branch_exists(_branch_name(self.batch_id, unit_id)))

    def test_worktree_unit_json_is_seeded_with_metadata(self):
        batch = _batch_result(
            self.batch_id,
            [_unit("unit_x", phase_id="PHASE_042", touches_paths=["src/x.ts", "tests/x/**"])],
        )
        dispatch_batch(batch, root=self.temp_dir)

        unit_json = self.temp_dir / _worktree_relpath(self.batch_id, "unit_x") / ".harness" / "WORKTREE_UNIT.json"
        self.assertTrue(unit_json.exists(), f"WORKTREE_UNIT.json missing: {unit_json}")

        with open(unit_json, "r", encoding="utf-8") as f:
            seeded = json.load(f)
        self.assertEqual(seeded["batch_id"], self.batch_id)
        self.assertEqual(seeded["unit_id"], "unit_x")
        self.assertEqual(seeded["phase_id"], "PHASE_042")
        self.assertEqual(seeded["touches_paths"], ["src/x.ts", "tests/x/**"])

    def test_fleet_entries_have_v2_shape(self):
        batch = _batch_result(self.batch_id, [_unit("u1", phase_id="PHASE_999", touches_paths=["src/**"])])
        result = dispatch_batch(batch, root=self.temp_dir, now="2026-04-20T00:30:00Z")

        (entry,) = result["fleet"]["units"]
        self.assertEqual(
            set(entry.keys()),
            {
                "unit_id",
                "phase_id",
                "worktree_path",
                "branch",
                "status",
                "started_at",
                "ended_at",
                "agent_summary_path",
                "conflict",
            },
        )
        self.assertEqual(entry["status"], "running")
        self.assertEqual(entry["started_at"], "2026-04-20T00:30:00Z")
        self.assertIsNone(entry["ended_at"])
        self.assertIsNone(entry["agent_summary_path"])
        self.assertIsNone(entry["conflict"])
        self.assertEqual(entry["worktree_path"], _worktree_relpath(self.batch_id, "u1"))
        self.assertEqual(entry["branch"], _branch_name(self.batch_id, "u1"))

    def test_empty_batch_produces_empty_fleet(self):
        batch = _batch_result(self.batch_id, [])
        result = dispatch_batch(batch, root=self.temp_dir)
        self.assertEqual(result["fleet"]["mode"], "dispatched")
        self.assertEqual(result["fleet"]["batch_id"], self.batch_id)
        self.assertEqual(result["fleet"]["units"], [])

    def test_state_fleet_is_written_in_place_when_state_provided(self):
        batch = _batch_result(self.batch_id, [_unit("u1", touches_paths=["src/**"])])
        state = {"execution": {"active_phase": "PHASE_X", "fleet": {"mode": "idle"}}}
        dispatch_batch(batch, root=self.temp_dir, state=state)

        self.assertEqual(state["execution"]["fleet"]["mode"], "dispatched")
        self.assertEqual(state["execution"]["fleet"]["batch_id"], self.batch_id)
        self.assertEqual(len(state["execution"]["fleet"]["units"]), 1)
        # Pre-existing execution keys are preserved.
        self.assertEqual(state["execution"]["active_phase"], "PHASE_X")


class TestAtomicRollback(DispatchBatchTestBase):
    def test_branch_collision_on_second_unit_rolls_back_first(self):
        # Pre-create the branch name the *second* unit would use so that
        # `git worktree add -b` for unit_b fails and rollback must remove
        # unit_a's successful worktree.
        colliding_branch = _branch_name(self.batch_id, "unit_b")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "branch", colliding_branch],
            check=True,
        )

        batch = _batch_result(
            self.batch_id,
            [_unit("unit_a", touches_paths=["src/a/**"]), _unit("unit_b", touches_paths=["src/b/**"])],
        )

        with self.assertRaises(DispatchError):
            dispatch_batch(batch, root=self.temp_dir)

        # Rollback evidence: unit_a's worktree is gone and its branch is deleted.
        wt_a = self.temp_dir / _worktree_relpath(self.batch_id, "unit_a")
        self.assertFalse(wt_a.exists(), f"unit_a worktree should be rolled back: {wt_a}")
        self.assertFalse(
            self._branch_exists(_branch_name(self.batch_id, "unit_a")),
            "unit_a branch should be deleted after rollback",
        )
        # The pre-existing unit_b branch (the collision source) is left alone.
        self.assertTrue(
            self._branch_exists(colliding_branch),
            "pre-existing unit_b branch should NOT be deleted by rollback",
        )

    def test_missing_id_on_unit_rolls_back_prior_worktree(self):
        # A malformed unit entry (KeyError on `id`) after a successful one
        # must still trigger the rollback path, not leave the first
        # worktree dangling.
        batch = _batch_result(
            self.batch_id,
            [
                _unit("unit_a", touches_paths=["src/a/**"]),
                {"phase_id": "PHASE_X", "touches_paths": []},  # no "id"
            ],
        )

        with self.assertRaises(DispatchError):
            dispatch_batch(batch, root=self.temp_dir)

        wt_a = self.temp_dir / _worktree_relpath(self.batch_id, "unit_a")
        self.assertFalse(wt_a.exists())
        self.assertFalse(self._branch_exists(_branch_name(self.batch_id, "unit_a")))


class TestCliSmoke(DispatchBatchTestBase):
    def setUp(self):
        super().setUp()
        # Minimal .harness/ with a state.json the CLI can update in place.
        (self.temp_dir / ".harness").mkdir(exist_ok=True)
        self.state_path = self.temp_dir / ".harness" / "state.json"
        self.state_path.write_text(
            json.dumps({"execution": {"active_phase": "PHASE_X", "fleet": {"mode": "idle"}}}, indent=2),
            encoding="utf-8",
        )

    def test_cli_writes_updated_state_and_prints_result(self):
        batch_path = self.temp_dir / "batch.json"
        batch_path.write_text(
            json.dumps(_batch_result(self.batch_id, [_unit("u1", touches_paths=["src/**"])])),
            encoding="utf-8",
        )

        env = os.environ.copy()
        result = subprocess.run(
            [
                sys.executable,
                str(DISPATCH_SCRIPT),
                "--batch",
                str(batch_path),
                "--root",
                str(self.temp_dir),
                "--state",
                str(self.state_path),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        payload = json.loads(result.stdout)
        self.assertEqual(payload["batch_id"], self.batch_id)
        self.assertEqual(payload["fleet"]["mode"], "dispatched")
        self.assertEqual(len(payload["fleet"]["units"]), 1)

        with open(self.state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state["execution"]["fleet"]["mode"], "dispatched")
        self.assertEqual(state["execution"]["fleet"]["batch_id"], self.batch_id)
        self.assertIn("last_updated", state)

    def test_cli_help_runs(self):
        result = subprocess.run(
            [sys.executable, str(DISPATCH_SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--batch", result.stdout)
        self.assertIn("--root", result.stdout)
        self.assertIn("--state", result.stdout)


if __name__ == "__main__":
    unittest.main()
