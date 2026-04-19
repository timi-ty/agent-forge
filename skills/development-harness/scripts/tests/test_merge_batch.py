"""Tests for merge_batch.py -- unit 020 scope.

Each test builds a throwaway git repo in a temp dir. Per-unit branches
are created directly (no worktree) for most cases because the behaviors
under test are merge semantics, not worktree lifecycle. One end-to-end
case uses dispatch_batch to cover the worktree-removal path after a
successful merge.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dispatch_batch import dispatch_batch  # noqa: E402
from merge_batch import (  # noqa: E402
    MergeError,
    merge_batch,
)

SCRIPT_DIR = Path(__file__).resolve().parent.parent
MERGE_SCRIPT = SCRIPT_DIR / "merge_batch.py"


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
        ["git", "-C", str(root), "commit", "-q", "-m", "initial commit"], check=True
    )


def _create_branch_with_file(root, branch, file_rel, contents):
    """Create ``branch`` from main with one commit adding ``file_rel``."""
    subprocess.run(
        ["git", "-C", str(root), "checkout", "-q", "-b", branch, "main"], check=True
    )
    target = Path(root) / file_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(contents, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", file_rel], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", f"add {file_rel}"], check=True
    )
    subprocess.run(
        ["git", "-C", str(root), "checkout", "-q", "main"], check=True
    )


def _fleet_unit(unit_id, batch_id, phase_id="PHASE_X"):
    return {
        "unit_id": unit_id,
        "phase_id": phase_id,
        "worktree_path": f".harness/worktrees/{batch_id}/{unit_id}",
        "branch": f"harness/{batch_id}/{unit_id}",
        "status": "running",
        "started_at": "2026-04-20T00:45:00Z",
        "ended_at": None,
        "agent_summary_path": None,
        "conflict": None,
    }


def _fleet_state(batch_id, units):
    return {
        "execution": {
            "fleet": {
                "mode": "dispatched",
                "batch_id": batch_id,
                "units": list(units),
            }
        }
    }


def _branch_exists(root, branch):
    res = subprocess.run(
        ["git", "-C", str(root), "show-ref", "--verify", f"refs/heads/{branch}"],
        capture_output=True, text=True,
    )
    return res.returncode == 0


def _log_subjects(root):
    res = subprocess.run(
        ["git", "-C", str(root), "log", "--format=%s"],
        capture_output=True, text=True, check=True,
    )
    return res.stdout.splitlines()


class MergeBatchBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True)
        )
        _init_repo(self.temp_dir)
        self.batch_id = "batch_2026-04-20T00-45-00Z"


class TestHappyPath(MergeBatchBase):
    def _setup_non_overlapping_units(self, unit_ids):
        for uid in unit_ids:
            _create_branch_with_file(
                self.temp_dir,
                f"harness/{self.batch_id}/{uid}",
                f"src/{uid}.txt",
                f"hello from {uid}\n",
            )

    def test_all_units_merge_cleanly(self):
        self._setup_non_overlapping_units(["u1", "u2", "u3"])
        state = _fleet_state(
            self.batch_id,
            [_fleet_unit(u, self.batch_id) for u in ("u1", "u2", "u3")],
        )
        result = merge_batch(state, root=self.temp_dir, now="2026-04-20T00:46:00Z")

        self.assertEqual(result["outcome"], "ok")
        self.assertEqual(result["merged"], ["u1", "u2", "u3"])
        self.assertEqual(result["conflicted"], [])
        self.assertEqual(result["skipped"], [])

        for unit in state["execution"]["fleet"]["units"]:
            self.assertEqual(unit["status"], "merged")
            self.assertEqual(unit["ended_at"], "2026-04-20T00:46:00Z")
            self.assertIsNone(unit["conflict"])

        self.assertEqual(state["execution"]["fleet"]["mode"], "idle")

    def test_merge_commits_land_on_main_with_expected_messages(self):
        self._setup_non_overlapping_units(["u1", "u2"])
        state = _fleet_state(
            self.batch_id,
            [_fleet_unit(u, self.batch_id) for u in ("u1", "u2")],
        )
        merge_batch(state, root=self.temp_dir)

        subjects = _log_subjects(self.temp_dir)
        # Newest first: merge u2, merge u1, then the two branch tip adds,
        # then initial commit.
        self.assertIn("harness: merge u2", subjects)
        self.assertIn("harness: merge u1", subjects)
        self.assertLess(subjects.index("harness: merge u2"), subjects.index("harness: merge u1"))

    def test_merged_unit_branches_are_deleted(self):
        self._setup_non_overlapping_units(["u1", "u2"])
        state = _fleet_state(
            self.batch_id,
            [_fleet_unit(u, self.batch_id) for u in ("u1", "u2")],
        )
        merge_batch(state, root=self.temp_dir)

        self.assertFalse(_branch_exists(self.temp_dir, f"harness/{self.batch_id}/u1"))
        self.assertFalse(_branch_exists(self.temp_dir, f"harness/{self.batch_id}/u2"))

    def test_empty_fleet_returns_empty_outcome(self):
        state = _fleet_state(self.batch_id, [])
        result = merge_batch(state, root=self.temp_dir)
        self.assertEqual(result["outcome"], "empty")
        self.assertEqual(result["merged"], [])
        self.assertEqual(state["execution"]["fleet"]["mode"], "idle")

    def test_fleet_mode_transitions_to_idle(self):
        self._setup_non_overlapping_units(["u1"])
        state = _fleet_state(self.batch_id, [_fleet_unit("u1", self.batch_id)])
        self.assertEqual(state["execution"]["fleet"]["mode"], "dispatched")
        merge_batch(state, root=self.temp_dir)
        self.assertEqual(state["execution"]["fleet"]["mode"], "idle")


class TestAbortBatchStrategy(MergeBatchBase):
    def _setup_conflicting_units(self):
        # u1 and u2 both write the same file -> u2 conflicts with u1.
        # u3 is disjoint and would be mergeable, but abort_batch skips it.
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u1", "src/shared.txt", "version A\n"
        )
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u2", "src/shared.txt", "version B\n"
        )
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u3", "src/other.txt", "version C\n"
        )

    def test_first_conflict_aborts_batch_and_skips_remaining(self):
        self._setup_conflicting_units()
        state = _fleet_state(
            self.batch_id,
            [_fleet_unit(u, self.batch_id) for u in ("u1", "u2", "u3")],
        )
        result = merge_batch(
            state, root=self.temp_dir, conflict_strategy="abort_batch"
        )

        self.assertEqual(result["outcome"], "aborted")
        self.assertEqual(result["merged"], ["u1"])
        self.assertEqual(result["conflicted"], ["u2"])
        self.assertEqual(result["skipped"], ["u3"])

        units = state["execution"]["fleet"]["units"]
        self.assertEqual(units[0]["status"], "merged")
        self.assertEqual(units[1]["status"], "failed")
        self.assertEqual(units[2]["status"], "failed")

        # u2 carries conflict metadata; u3 was skipped and has conflict=None.
        self.assertIsNotNone(units[1]["conflict"])
        self.assertEqual(units[1]["conflict"]["strategy_applied"], "abort_batch")
        self.assertIn("src/shared.txt", units[1]["conflict"]["paths"])
        self.assertIsNone(units[2]["conflict"])

    def test_abort_batch_leaves_merged_branch_cleaned_but_conflict_branch_intact(self):
        self._setup_conflicting_units()
        state = _fleet_state(
            self.batch_id,
            [_fleet_unit(u, self.batch_id) for u in ("u1", "u2", "u3")],
        )
        merge_batch(state, root=self.temp_dir, conflict_strategy="abort_batch")

        # u1 merged cleanly -> its branch is deleted.
        self.assertFalse(_branch_exists(self.temp_dir, f"harness/{self.batch_id}/u1"))
        # u2 conflicted, u3 was skipped -> branches remain for recovery.
        self.assertTrue(_branch_exists(self.temp_dir, f"harness/{self.batch_id}/u2"))
        self.assertTrue(_branch_exists(self.temp_dir, f"harness/{self.batch_id}/u3"))


class TestSerializeConflictedStrategy(MergeBatchBase):
    def test_conflicted_unit_stays_running_and_remaining_units_proceed(self):
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u1", "src/shared.txt", "version A\n"
        )
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u2", "src/shared.txt", "version B\n"
        )
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u3", "src/other.txt", "version C\n"
        )
        state = _fleet_state(
            self.batch_id,
            [_fleet_unit(u, self.batch_id) for u in ("u1", "u2", "u3")],
        )

        result = merge_batch(
            state,
            root=self.temp_dir,
            conflict_strategy="serialize_conflicted",
        )

        self.assertEqual(result["outcome"], "partial")
        self.assertEqual(result["merged"], ["u1", "u3"])
        self.assertEqual(result["conflicted"], ["u2"])
        self.assertEqual(result["skipped"], [])

        units = state["execution"]["fleet"]["units"]
        self.assertEqual(units[0]["status"], "merged")
        self.assertEqual(units[1]["status"], "running")
        self.assertEqual(units[1]["conflict"]["strategy_applied"], "serialize_conflicted")
        self.assertEqual(units[2]["status"], "merged")

    def test_serialize_conflicted_preserves_conflicted_branch(self):
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u1", "src/shared.txt", "version A\n"
        )
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u2", "src/shared.txt", "version B\n"
        )
        state = _fleet_state(
            self.batch_id,
            [_fleet_unit(u, self.batch_id) for u in ("u1", "u2")],
        )
        merge_batch(
            state,
            root=self.temp_dir,
            conflict_strategy="serialize_conflicted",
        )

        # u1 merged cleanly -> branch gone. u2 conflicted and is deferred
        # under serialize_conflicted -> branch must remain for the next batch.
        self.assertFalse(_branch_exists(self.temp_dir, f"harness/{self.batch_id}/u1"))
        self.assertTrue(_branch_exists(self.temp_dir, f"harness/{self.batch_id}/u2"))


class TestPostMergeValidation(MergeBatchBase):
    def _setup_two_units(self):
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u1", "src/u1.txt", "u1\n"
        )
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u2", "src/u2.txt", "u2\n"
        )
        return _fleet_state(
            self.batch_id,
            [_fleet_unit(u, self.batch_id) for u in ("u1", "u2")],
        )

    def test_validator_is_called_with_merged_unit_ids(self):
        state = self._setup_two_units()
        calls = []

        def recorder(root, merged_ids):
            calls.append((str(root), list(merged_ids)))
            return True, "ok"

        merge_batch(
            state,
            root=self.temp_dir,
            run_post_merge_validation=recorder,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], ["u1", "u2"])

    def test_validation_failure_triggers_reset_hard_rollback(self):
        state = self._setup_two_units()
        pre_head = subprocess.run(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        def failing_validator(root, merged_ids):
            return False, "tests fail: 3 failing in tests/auth.test.ts"

        result = merge_batch(
            state,
            root=self.temp_dir,
            run_post_merge_validation=failing_validator,
        )

        self.assertEqual(result["outcome"], "validation_failed")
        self.assertEqual(result["merged"], [])
        self.assertEqual(result["validation_evidence"], "tests fail: 3 failing in tests/auth.test.ts")

        post_head = subprocess.run(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertEqual(post_head, pre_head, "HEAD should be back at pre-merge ref")

        # Both units should be downgraded to 'failed' with the dedicated
        # post_merge_validation_failed conflict marker.
        for unit in state["execution"]["fleet"]["units"]:
            self.assertEqual(unit["status"], "failed")
            self.assertEqual(
                unit["conflict"]["strategy_applied"], "post_merge_validation_failed"
            )

    def test_validator_not_called_when_nothing_merged(self):
        # Set up two conflicting units with abort_batch so nothing merges.
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u1", "src/shared.txt", "A\n"
        )
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u2", "src/shared.txt", "B\n"
        )
        # Poison main so u1 conflicts on first attempt.
        (self.temp_dir / "src").mkdir(exist_ok=True)
        (self.temp_dir / "src" / "shared.txt").write_text("main's version\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "src/shared.txt"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-q", "-m", "poison main"],
            check=True,
        )

        state = _fleet_state(
            self.batch_id,
            [_fleet_unit(u, self.batch_id) for u in ("u1", "u2")],
        )
        calls = []

        def recorder(root, merged_ids):
            calls.append(list(merged_ids))
            return True, "ok"

        merge_batch(
            state,
            root=self.temp_dir,
            conflict_strategy="abort_batch",
            run_post_merge_validation=recorder,
        )
        self.assertEqual(calls, [], "validator must not run when no unit merged")


class TestStrategyValidation(MergeBatchBase):
    def test_unknown_conflict_strategy_raises(self):
        state = _fleet_state(self.batch_id, [_fleet_unit("u1", self.batch_id)])
        with self.assertRaises(MergeError):
            merge_batch(state, root=self.temp_dir, conflict_strategy="bogus")


class TestEndToEndWithDispatch(MergeBatchBase):
    """One integration-style case exercising dispatch_batch + merge_batch together."""

    def test_dispatch_then_merge_cleans_up_worktrees(self):
        batch_result = {
            "batch_id": self.batch_id,
            "batch": [
                {"id": "u1", "phase_id": "PHASE_X", "touches_paths": ["src/u1.txt"]},
                {"id": "u2", "phase_id": "PHASE_X", "touches_paths": ["src/u2.txt"]},
            ],
            "excluded": [],
        }
        state = {}
        dispatch_batch(batch_result, root=self.temp_dir, state=state)

        # Worktrees exist on disk now.
        for uid in ("u1", "u2"):
            wt = self.temp_dir / f".harness/worktrees/{self.batch_id}/{uid}"
            self.assertTrue(wt.is_dir())

        # Commit a file in each worktree so merge has something to fan-in.
        for uid in ("u1", "u2"):
            wt = self.temp_dir / f".harness/worktrees/{self.batch_id}/{uid}"
            (wt / f"src").mkdir(exist_ok=True)
            (wt / "src" / f"{uid}.txt").write_text(f"{uid}\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(wt), "add", f"src/{uid}.txt"], check=True
            )
            subprocess.run(
                ["git", "-C", str(wt), "commit", "-q", "-m", f"add {uid}"], check=True
            )

        result = merge_batch(state, root=self.temp_dir)
        self.assertEqual(result["outcome"], "ok")
        self.assertEqual(result["merged"], ["u1", "u2"])

        for uid in ("u1", "u2"):
            wt = self.temp_dir / f".harness/worktrees/{self.batch_id}/{uid}"
            self.assertFalse(wt.exists(), f"worktree should be cleaned up: {wt}")
            self.assertFalse(_branch_exists(self.temp_dir, f"harness/{self.batch_id}/{uid}"))


class TestCliSmoke(MergeBatchBase):
    def test_cli_help_runs(self):
        result = subprocess.run(
            [sys.executable, str(MERGE_SCRIPT), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--state", result.stdout)
        self.assertIn("--root", result.stdout)
        self.assertIn("--conflict-strategy", result.stdout)

    def test_cli_merges_fleet_and_writes_state(self):
        _create_branch_with_file(
            self.temp_dir, f"harness/{self.batch_id}/u1", "src/u1.txt", "u1\n"
        )
        state_path = self.temp_dir / "state.json"
        state_path.write_text(
            json.dumps(_fleet_state(self.batch_id, [_fleet_unit("u1", self.batch_id)])),
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable, str(MERGE_SCRIPT),
                "--state", str(state_path),
                "--root", str(self.temp_dir),
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["outcome"], "ok")
        self.assertEqual(payload["merged"], ["u1"])

        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["execution"]["fleet"]["mode"], "idle")
        self.assertIn("last_updated", persisted)


if __name__ == "__main__":
    unittest.main()
