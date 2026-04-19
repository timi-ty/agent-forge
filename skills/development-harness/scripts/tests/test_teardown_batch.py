"""Tests for teardown_batch.py -- unit 021 scope.

Idempotence is the core property: running the cleanup twice must be a
no-op on the second call. Tests build a real git repo + dispatch a
batch via dispatch_batch, then exercise teardown in both scoped and
global modes. Missing-worktree and missing-branch paths are covered
with crafted states where git's internal view is out of sync with
disk.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dispatch_batch import dispatch_batch  # noqa: E402
from teardown_batch import teardown_batch  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent.parent
TEARDOWN_SCRIPT = SCRIPT_DIR / "teardown_batch.py"


def _init_repo(root):
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "harness@test.local"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Harness Test"], check=True
    )
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "initial"], check=True
    )


def _dispatch(root, batch_id, unit_ids):
    """Dispatch a minimal batch and return the fleet state dict."""
    batch_result = {
        "batch_id": batch_id,
        "batch": [{"id": uid, "phase_id": "PHASE_X", "touches_paths": [f"src/{uid}.txt"]} for uid in unit_ids],
        "excluded": [],
    }
    state = {}
    dispatch_batch(batch_result, root=root, state=state)
    return state


def _branch_exists(root, branch):
    res = subprocess.run(
        ["git", "-C", str(root), "show-ref", "--verify", f"refs/heads/{branch}"],
        capture_output=True, text=True,
    )
    return res.returncode == 0


class TeardownBatchBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True)
        )
        _init_repo(self.temp_dir)


class TestScopedTeardown(TeardownBatchBase):
    def test_single_batch_teardown_removes_worktrees_and_branches(self):
        batch_id = "batch_2026-04-20T01-30-00Z"
        _dispatch(self.temp_dir, batch_id, ["u1", "u2"])

        # Pre-conditions.
        for uid in ("u1", "u2"):
            self.assertTrue(
                (self.temp_dir / ".harness" / "worktrees" / batch_id / uid).is_dir()
            )
            self.assertTrue(_branch_exists(self.temp_dir, f"harness/{batch_id}/{uid}"))

        result = teardown_batch(self.temp_dir, batch_id=batch_id)

        self.assertEqual(len(result["removed_worktrees"]), 2)
        self.assertEqual(
            sorted(result["deleted_branches"]),
            [f"harness/{batch_id}/u1", f"harness/{batch_id}/u2"],
        )
        self.assertEqual(result["batch_ids"], [batch_id])

        # Post-conditions.
        self.assertFalse((self.temp_dir / ".harness" / "worktrees" / batch_id).exists())
        for uid in ("u1", "u2"):
            self.assertFalse(_branch_exists(self.temp_dir, f"harness/{batch_id}/{uid}"))

    def test_second_run_is_a_no_op(self):
        batch_id = "batch_idempotent"
        _dispatch(self.temp_dir, batch_id, ["u1"])
        first = teardown_batch(self.temp_dir, batch_id=batch_id)
        self.assertEqual(len(first["removed_worktrees"]), 1)
        self.assertEqual(len(first["deleted_branches"]), 1)

        second = teardown_batch(self.temp_dir, batch_id=batch_id)
        self.assertEqual(second["removed_worktrees"], [])
        self.assertEqual(second["deleted_branches"], [])
        # The batch_id shouldn't appear in the second run's summary since
        # nothing was left to clean up.
        self.assertEqual(second["batch_ids"], [])

    def test_scoped_teardown_leaves_other_batches_alone(self):
        batch_a = "batch_AAAA"
        batch_b = "batch_BBBB"
        _dispatch(self.temp_dir, batch_a, ["u1"])
        _dispatch(self.temp_dir, batch_b, ["u1"])

        result = teardown_batch(self.temp_dir, batch_id=batch_a)
        self.assertEqual(result["batch_ids"], [batch_a])

        # batch_a is gone, batch_b is intact.
        self.assertFalse(
            (self.temp_dir / ".harness" / "worktrees" / batch_a).exists()
        )
        self.assertTrue(
            (self.temp_dir / ".harness" / "worktrees" / batch_b / "u1").is_dir()
        )
        self.assertTrue(_branch_exists(self.temp_dir, f"harness/{batch_b}/u1"))

    def test_scoped_teardown_for_unknown_batch_is_a_no_op(self):
        # Dispatch a real batch so worktrees dir exists, then scope teardown
        # to an id that was never dispatched.
        _dispatch(self.temp_dir, "batch_real", ["u1"])
        result = teardown_batch(self.temp_dir, batch_id="batch_phantom")
        self.assertEqual(result["removed_worktrees"], [])
        self.assertEqual(result["deleted_branches"], [])
        self.assertEqual(result["batch_ids"], [])
        # batch_real is untouched.
        self.assertTrue(_branch_exists(self.temp_dir, "harness/batch_real/u1"))


class TestGlobalTeardown(TeardownBatchBase):
    def test_global_teardown_removes_every_batch(self):
        batch_a = "batch_A"
        batch_b = "batch_B"
        _dispatch(self.temp_dir, batch_a, ["u1", "u2"])
        _dispatch(self.temp_dir, batch_b, ["u3"])

        result = teardown_batch(self.temp_dir, batch_id=None)
        self.assertEqual(len(result["removed_worktrees"]), 3)
        self.assertEqual(len(result["deleted_branches"]), 3)
        self.assertEqual(sorted(result["batch_ids"]), sorted([batch_a, batch_b]))

        # worktrees dir gone, every harness branch gone.
        self.assertFalse((self.temp_dir / ".harness" / "worktrees").exists())
        for branch in (
            f"harness/{batch_a}/u1",
            f"harness/{batch_a}/u2",
            f"harness/{batch_b}/u3",
        ):
            self.assertFalse(_branch_exists(self.temp_dir, branch))

    def test_global_teardown_on_clean_repo_is_a_no_op(self):
        # No batches ever dispatched; teardown must still succeed.
        result = teardown_batch(self.temp_dir, batch_id=None)
        self.assertEqual(result["removed_worktrees"], [])
        self.assertEqual(result["deleted_branches"], [])
        self.assertEqual(result["batch_ids"], [])


class TestMissingStateTolerance(TeardownBatchBase):
    def test_orphaned_branch_without_worktree_is_cleaned_up(self):
        # Create a harness/<batch>/<unit> branch directly -- no worktree on
        # disk. Teardown should still delete the branch.
        orphan_batch = "batch_orphan"
        orphan_branch = f"harness/{orphan_batch}/u1"
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "branch", orphan_branch],
            check=True,
        )
        self.assertTrue(_branch_exists(self.temp_dir, orphan_branch))

        result = teardown_batch(self.temp_dir, batch_id=None)
        self.assertIn(orphan_branch, result["deleted_branches"])
        self.assertIn(orphan_batch, result["batch_ids"])
        self.assertFalse(_branch_exists(self.temp_dir, orphan_branch))

    def test_orphaned_worktree_dir_without_branch_is_cleaned_up(self):
        # Manually create an on-disk worktree directory that git doesn't
        # know about. Teardown should remove it.
        stale_batch = "batch_stale"
        stale_dir = self.temp_dir / ".harness" / "worktrees" / stale_batch / "u1"
        stale_dir.mkdir(parents=True)
        (stale_dir / "something.txt").write_text("residue\n", encoding="utf-8")

        result = teardown_batch(self.temp_dir, batch_id=stale_batch)
        self.assertFalse(stale_dir.exists())
        # No branch deletions are expected since no such branch exists.
        self.assertEqual(result["deleted_branches"], [])


class TestCliSmoke(TeardownBatchBase):
    def test_cli_help_runs(self):
        result = subprocess.run(
            [sys.executable, str(TEARDOWN_SCRIPT), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--batch-id", result.stdout)
        self.assertIn("--root", result.stdout)

    def test_cli_removes_batch_and_prints_summary(self):
        batch_id = "batch_cli"
        _dispatch(self.temp_dir, batch_id, ["u1"])

        result = subprocess.run(
            [
                sys.executable, str(TEARDOWN_SCRIPT),
                "--batch-id", batch_id,
                "--root", str(self.temp_dir),
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        payload = json.loads(result.stdout)
        self.assertEqual(payload["batch_ids"], [batch_id])
        self.assertEqual(len(payload["removed_worktrees"]), 1)
        self.assertEqual(len(payload["deleted_branches"]), 1)


if __name__ == "__main__":
    unittest.main()
