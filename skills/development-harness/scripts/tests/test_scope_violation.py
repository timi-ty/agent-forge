"""Tests for the scope-violation detector -- unit 022 scope.

The detector runs inside merge_batch.py before each unit's merge. It
reads the unit's declared touches_paths from WORKTREE_UNIT.json (seeded
by dispatch_batch), computes `git diff --name-only <merge-base>..<branch>`,
and rejects any unit whose diff includes a file matching NONE of the
declared globs. The sub-agent's self-report is never trusted.

Tests build real git repos in tempdirs because the detector shells out
to `git diff`. Both the helper functions and the integrated merge_batch
behavior are exercised.
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
    _is_within_scope,
    _read_worktree_touches_paths,
    _scope_violations,
    merge_batch,
)


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


def _create_branch_with_files(root, branch, file_map):
    """Create `branch` off main, committing every file in file_map."""
    subprocess.run(
        ["git", "-C", str(root), "checkout", "-q", "-b", branch, "main"], check=True
    )
    for rel, body in file_map.items():
        target = Path(root) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", rel], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", f"populate {branch}"], check=True
    )
    subprocess.run(
        ["git", "-C", str(root), "checkout", "-q", "main"], check=True
    )


def _branch_exists(root, branch):
    res = subprocess.run(
        ["git", "-C", str(root), "show-ref", "--verify", f"refs/heads/{branch}"],
        capture_output=True, text=True,
    )
    return res.returncode == 0


def _fleet_unit(unit_id, batch_id, phase_id="PHASE_X"):
    return {
        "unit_id": unit_id,
        "phase_id": phase_id,
        "worktree_path": f".harness/worktrees/{batch_id}/{unit_id}",
        "branch": f"harness/{batch_id}/{unit_id}",
        "status": "running",
        "started_at": "2026-04-20T01:30:00Z",
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


class TestIsWithinScope(unittest.TestCase):
    def test_literal_match(self):
        self.assertTrue(_is_within_scope("src/auth.ts", ["src/auth.ts"]))

    def test_glob_match_recursive(self):
        self.assertTrue(_is_within_scope("src/auth/login/handler.ts", ["src/auth/**"]))

    def test_glob_match_non_recursive(self):
        self.assertTrue(_is_within_scope("src/auth.ts", ["src/*.ts"]))

    def test_non_match_outside_scope(self):
        self.assertFalse(_is_within_scope("src/users.ts", ["src/auth/**"]))

    def test_empty_scope_rejects_every_file(self):
        self.assertFalse(_is_within_scope("README.md", []))

    def test_multiple_globs_any_match_wins(self):
        self.assertTrue(
            _is_within_scope(
                "tests/auth/login.test.ts",
                ["src/auth/**", "tests/auth/**"],
            )
        )


class ScopeBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True)
        )
        _init_repo(self.temp_dir)
        self.batch_id = "batch_2026-04-20T01-30-00Z"


class TestScopeViolationsHelper(ScopeBase):
    def test_in_scope_branch_returns_no_violations(self):
        branch = f"harness/{self.batch_id}/u1"
        _create_branch_with_files(
            self.temp_dir,
            branch,
            {"src/auth/login.ts": "login\n", "src/auth/logout.ts": "logout\n"},
        )
        violations = _scope_violations(
            self.temp_dir, branch, ["src/auth/**"]
        )
        self.assertEqual(violations, [])

    def test_out_of_scope_files_are_returned(self):
        branch = f"harness/{self.batch_id}/u1"
        _create_branch_with_files(
            self.temp_dir,
            branch,
            {
                "src/auth/login.ts": "login\n",
                "src/users/handler.ts": "users\n",
                "docs/migration.md": "docs\n",
            },
        )
        violations = _scope_violations(
            self.temp_dir, branch, ["src/auth/**"]
        )
        self.assertEqual(
            sorted(violations),
            ["docs/migration.md", "src/users/handler.ts"],
        )

    def test_empty_touches_paths_flags_every_changed_file(self):
        branch = f"harness/{self.batch_id}/u1"
        _create_branch_with_files(
            self.temp_dir, branch, {"src/anything.ts": "x\n"}
        )
        violations = _scope_violations(self.temp_dir, branch, [])
        self.assertEqual(violations, ["src/anything.ts"])

    def test_unknown_branch_yields_empty_list(self):
        # No branch named this; git merge-base fails. Helper returns [].
        violations = _scope_violations(
            self.temp_dir, "harness/nope/ghost", ["src/**"]
        )
        self.assertEqual(violations, [])


class TestReadWorktreeTouchesPaths(ScopeBase):
    def test_reads_touches_paths_seeded_by_dispatch(self):
        batch_result = {
            "batch_id": self.batch_id,
            "batch": [
                {"id": "u1", "phase_id": "PHASE_X", "touches_paths": ["src/auth/**"]},
            ],
            "excluded": [],
        }
        dispatch_batch(batch_result, root=self.temp_dir, state={})

        touches = _read_worktree_touches_paths(
            self.temp_dir, f".harness/worktrees/{self.batch_id}/u1"
        )
        self.assertEqual(touches, ["src/auth/**"])

    def test_missing_sentinel_returns_none(self):
        # Worktree directory doesn't exist -- sentinel file is absent.
        touches = _read_worktree_touches_paths(
            self.temp_dir, f".harness/worktrees/{self.batch_id}/ghost"
        )
        self.assertIsNone(touches)

    def test_empty_touches_paths_returns_empty_list_not_none(self):
        batch_result = {
            "batch_id": self.batch_id,
            "batch": [
                {"id": "u1", "phase_id": "PHASE_X", "touches_paths": []},
            ],
            "excluded": [],
        }
        dispatch_batch(batch_result, root=self.temp_dir, state={})

        touches = _read_worktree_touches_paths(
            self.temp_dir, f".harness/worktrees/{self.batch_id}/u1"
        )
        self.assertEqual(touches, [])


class TestMergeBatchRejectsScopeViolator(ScopeBase):
    """End-to-end: a unit whose branch touches out-of-scope files is
    rejected before merge, and its rejection does not block other
    well-scoped units in the same batch."""

    def _dispatch_and_commit(self, unit_id, declared_paths, changed_files):
        """Dispatch one unit, then commit `changed_files` inside its worktree.

        Returns the full batch_result's fleet entry (already wired into
        the returned state mutation).
        """
        batch_result = {
            "batch_id": self.batch_id,
            "batch": [
                {
                    "id": unit_id,
                    "phase_id": "PHASE_X",
                    "touches_paths": list(declared_paths),
                }
            ],
            "excluded": [],
        }
        state = {}
        dispatch_batch(batch_result, root=self.temp_dir, state=state)

        worktree = self.temp_dir / f".harness/worktrees/{self.batch_id}/{unit_id}"
        for rel, body in changed_files.items():
            target = worktree / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(worktree), "add", rel], check=True
            )
        subprocess.run(
            ["git", "-C", str(worktree), "commit", "-q", "-m", f"work on {unit_id}"],
            check=True,
        )
        return state["execution"]["fleet"]["units"][0]

    def test_unit_writing_outside_scope_is_rejected_before_merge(self):
        # u1 declares src/auth/** but touches src/users/handler.ts (out of scope).
        offender = self._dispatch_and_commit(
            "u1",
            declared_paths=["src/auth/**"],
            changed_files={
                "src/auth/login.ts": "login\n",
                "src/users/handler.ts": "users\n",  # out of declared scope
            },
        )

        # Record HEAD before merge; if the detector works, HEAD must not
        # advance because no merge was attempted.
        pre_head = subprocess.run(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        state = _fleet_state(self.batch_id, [offender])
        result = merge_batch(state, root=self.temp_dir)

        self.assertEqual(result["outcome"], "all_conflicted")
        self.assertEqual(result["merged"], [])
        self.assertEqual(result["conflicted"], ["u1"])

        entry = state["execution"]["fleet"]["units"][0]
        self.assertEqual(entry["status"], "failed")
        self.assertEqual(entry["conflict"]["category"], "scope_violation")
        self.assertIn("src/users/handler.ts", entry["conflict"]["paths"])
        self.assertNotIn("src/auth/login.ts", entry["conflict"]["paths"])

        # HEAD did not advance: no merge was attempted.
        post_head = subprocess.run(
            ["git", "-C", str(self.temp_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertEqual(post_head, pre_head)

        # The out-of-scope unit's branch is preserved (not deleted as a
        # merged branch would be) so an operator can inspect what it did.
        self.assertTrue(_branch_exists(self.temp_dir, f"harness/{self.batch_id}/u1"))

    def test_well_scoped_unit_merges_alongside_scope_violator(self):
        offender = self._dispatch_and_commit(
            "u_bad",
            declared_paths=["src/auth/**"],
            changed_files={
                "src/auth/login.ts": "login\n",
                "src/users/handler.ts": "escape\n",
            },
        )
        well_scoped = self._dispatch_and_commit(
            "u_good",
            declared_paths=["src/users/**"],
            changed_files={"src/users/queries.ts": "queries\n"},
        )

        state = _fleet_state(self.batch_id, [offender, well_scoped])
        result = merge_batch(state, root=self.temp_dir)

        # Scope violations do not trigger abort_batch: u_good still merges.
        self.assertEqual(result["outcome"], "partial")
        self.assertEqual(result["merged"], ["u_good"])
        self.assertEqual(result["conflicted"], ["u_bad"])

        units = state["execution"]["fleet"]["units"]
        self.assertEqual(units[0]["status"], "failed")
        self.assertEqual(units[0]["conflict"]["category"], "scope_violation")
        self.assertEqual(units[1]["status"], "merged")
        self.assertIsNone(units[1]["conflict"])

    def test_within_scope_changes_are_allowed_through(self):
        unit = self._dispatch_and_commit(
            "u1",
            declared_paths=["src/auth/**", "tests/auth/**"],
            changed_files={
                "src/auth/login.ts": "login\n",
                "tests/auth/login.test.ts": "test\n",
            },
        )
        state = _fleet_state(self.batch_id, [unit])
        result = merge_batch(state, root=self.temp_dir)
        self.assertEqual(result["outcome"], "ok")
        self.assertEqual(result["merged"], ["u1"])
        self.assertEqual(
            state["execution"]["fleet"]["units"][0]["status"], "merged"
        )


if __name__ == "__main__":
    unittest.main()
