"""PHASE_005 integration test -- unit 025.

End-to-end exercise of the worktree dispatch + merge pipeline on a
throwaway git repo:

  1. Build a fixture repo with an initial commit on ``main``.
  2. Define a 3-unit batch whose units touch disjoint file trees so
     they are guaranteed parallel-safe.
  3. ``dispatch_batch.py`` creates per-unit worktrees + branches and
     writes ``state.execution.fleet``.
  4. **Shell-scripted fake agents** simulate the sub-agents' work:
     inside each worktree, they create the files that unit declared
     in ``touches_paths`` and commit them to the worktree's branch.
  5. ``merge_batch.py`` fans the per-unit branches back into ``main``.
  6. Assertions: final fleet mode is ``idle``; every unit has
     ``status="merged"``; every unit's files are present on ``main``
     with a ``harness: merge <unit_id>`` merge commit in the log; no
     ``.harness/worktrees/`` directory remains; no ``harness/batch_*/``
     branches remain.

Also exercises the mixed case (two well-scoped units + one scope
violator) so the integration path proves out the scope-detector as
well as the happy path.

Each test uses its own tempdir, so tests are independent.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The integration module lives two packages deep from scripts/; adjust
# the path so sibling modules (dispatch_batch, merge_batch) resolve the
# same way as in the unit-test files.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dispatch_batch import dispatch_batch  # noqa: E402
from merge_batch import merge_batch  # noqa: E402


def _init_repo(root):
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "harness@test.local"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Harness Integration"],
        check=True,
    )
    (root / "README.md").write_text(
        "phase-005 integration fixture\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "initial"], check=True
    )


def _fake_agent_commit(worktree_path, files):
    """Simulate a sub-agent: add files in the worktree and commit them.

    Mirrors what a real sub-agent would do inside its assigned worktree.
    Runs git add + commit via subprocess, scoped to the worktree's
    working tree.
    """
    for relpath, body in files.items():
        target = Path(worktree_path) / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(worktree_path), "add", relpath], check=True
        )
    subprocess.run(
        ["git", "-C", str(worktree_path), "commit", "-q",
         "-m", "sub-agent work"],
        check=True,
    )


def _branches_matching(root, prefix):
    res = subprocess.run(
        ["git", "-C", str(root), "branch", "--list",
         "--format=%(refname:short)"],
        capture_output=True, text=True, check=True,
    )
    return [b for b in res.stdout.splitlines() if b.startswith(prefix)]


def _log_subjects(root):
    res = subprocess.run(
        ["git", "-C", str(root), "log", "--format=%s"],
        capture_output=True, text=True, check=True,
    )
    return res.stdout.splitlines()


def _file_on_main(root, rel):
    res = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"HEAD:{rel}"],
        capture_output=True, text=True,
    )
    return res.returncode == 0


class ParallelInvokeBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True)
        )
        _init_repo(self.temp_dir)
        self.batch_id = "batch_2026-04-20T02-55-00Z"


class TestParallelInvokeHappyPath(ParallelInvokeBase):
    """End-to-end: dispatch 3 disjoint units, fake-agent each one, merge all,
    verify final state and cleanup."""

    def test_three_unit_dispatch_merge_cycle(self):
        # ----- 1. Define the batch (mimics compute_parallel_batch output).
        batch_result = {
            "batch_id": self.batch_id,
            "batch": [
                {
                    "id": "unit_a",
                    "phase_id": "PHASE_INT",
                    "touches_paths": ["src/a/**"],
                },
                {
                    "id": "unit_b",
                    "phase_id": "PHASE_INT",
                    "touches_paths": ["src/b/**"],
                },
                {
                    "id": "unit_c",
                    "phase_id": "PHASE_INT",
                    "touches_paths": ["src/c/**"],
                },
            ],
            "excluded": [],
        }
        state = {}

        # ----- 2. Dispatch creates worktrees + branches + fleet state.
        dispatch_result = dispatch_batch(batch_result, root=self.temp_dir, state=state)
        self.assertEqual(dispatch_result["fleet"]["mode"], "dispatched")
        self.assertEqual(len(dispatch_result["fleet"]["units"]), 3)

        # ----- 3. Shell-scripted fake agents: commit canned files in each worktree.
        worktree_root = self.temp_dir / ".harness" / "worktrees" / self.batch_id
        for unit_id in ("unit_a", "unit_b", "unit_c"):
            wt = worktree_root / unit_id
            self.assertTrue(wt.is_dir(), f"worktree {wt} should exist after dispatch")
            _fake_agent_commit(
                wt,
                files={
                    # Each unit touches its own slice of src/ so the merges
                    # cannot conflict.
                    f"src/{unit_id[-1]}/main.ts": f"// {unit_id}\nexport const name = '{unit_id}';\n",
                    f"src/{unit_id[-1]}/util.ts": f"// {unit_id} util\n",
                },
            )

        # ----- 4. merge_batch fans the three branches back into main.
        merge_result = merge_batch(state, root=self.temp_dir)

        # ----- 5. Assertions on the fleet state + return shape.
        self.assertEqual(merge_result["outcome"], "ok")
        self.assertEqual(sorted(merge_result["merged"]), ["unit_a", "unit_b", "unit_c"])
        self.assertEqual(merge_result["conflicted"], [])
        self.assertEqual(merge_result["skipped"], [])

        fleet = state["execution"]["fleet"]
        self.assertEqual(fleet["mode"], "idle")
        for unit in fleet["units"]:
            self.assertEqual(unit["status"], "merged")
            self.assertIsNone(unit["conflict"])
            self.assertIsNotNone(unit["ended_at"])

        # ----- 6. Every unit's files live on main now.
        for unit_id in ("unit_a", "unit_b", "unit_c"):
            slice_ = unit_id[-1]
            self.assertTrue(
                _file_on_main(self.temp_dir, f"src/{slice_}/main.ts"),
                f"expected src/{slice_}/main.ts on main after merge of {unit_id}",
            )
            self.assertTrue(
                _file_on_main(self.temp_dir, f"src/{slice_}/util.ts"),
                f"expected src/{slice_}/util.ts on main after merge of {unit_id}",
            )

        # ----- 7. Merge commits with the expected messages exist on main.
        subjects = _log_subjects(self.temp_dir)
        for unit_id in ("unit_a", "unit_b", "unit_c"):
            self.assertIn(f"harness: merge {unit_id}", subjects)

        # ----- 8. No residual worktrees, no residual harness/batch_*/ branches.
        self.assertFalse(
            worktree_root.exists(),
            f"batch worktree dir should be cleaned up: {worktree_root}",
        )
        self.assertEqual(
            _branches_matching(self.temp_dir, f"harness/{self.batch_id}/"),
            [],
            "no harness/<batch_id>/* branches should remain after successful merge",
        )


class TestParallelInvokeWithScopeViolator(ParallelInvokeBase):
    """One scope-violator + two well-scoped units: the violator is rejected
    without a merge attempt; the other two merge cleanly. End-to-end."""

    def test_scope_violator_rejected_other_units_merge(self):
        batch_result = {
            "batch_id": self.batch_id,
            "batch": [
                # Well-scoped: declares src/x/** and touches only that.
                {
                    "id": "unit_good1",
                    "phase_id": "PHASE_INT",
                    "touches_paths": ["src/x/**"],
                },
                # Scope violator: declares src/y/** but touches src/y/ AND src/elsewhere/.
                {
                    "id": "unit_bad",
                    "phase_id": "PHASE_INT",
                    "touches_paths": ["src/y/**"],
                },
                # Well-scoped: declares src/z/** and touches only that.
                {
                    "id": "unit_good2",
                    "phase_id": "PHASE_INT",
                    "touches_paths": ["src/z/**"],
                },
            ],
            "excluded": [],
        }
        state = {}
        dispatch_batch(batch_result, root=self.temp_dir, state=state)

        worktree_root = self.temp_dir / ".harness" / "worktrees" / self.batch_id
        _fake_agent_commit(worktree_root / "unit_good1", {"src/x/feature.ts": "x\n"})
        _fake_agent_commit(
            worktree_root / "unit_bad",
            {
                "src/y/main.ts": "y\n",
                # Out-of-scope escape: unit_bad declared only src/y/**.
                "src/elsewhere/secrets.ts": "should not be merged\n",
            },
        )
        _fake_agent_commit(worktree_root / "unit_good2", {"src/z/feature.ts": "z\n"})

        result = merge_batch(state, root=self.temp_dir)

        # Outcome: partial -- 2 merged + 1 rejected (scope violation).
        self.assertEqual(result["outcome"], "partial")
        self.assertEqual(sorted(result["merged"]), ["unit_good1", "unit_good2"])
        self.assertEqual(result["conflicted"], ["unit_bad"])

        fleet_by_id = {u["unit_id"]: u for u in state["execution"]["fleet"]["units"]}
        self.assertEqual(fleet_by_id["unit_good1"]["status"], "merged")
        self.assertEqual(fleet_by_id["unit_good2"]["status"], "merged")
        self.assertEqual(fleet_by_id["unit_bad"]["status"], "failed")
        self.assertEqual(
            fleet_by_id["unit_bad"]["conflict"]["category"], "scope_violation"
        )
        self.assertIn(
            "src/elsewhere/secrets.ts",
            fleet_by_id["unit_bad"]["conflict"]["paths"],
        )

        # Good units' files landed on main; scope-violator's out-of-scope
        # file never did (because no merge was attempted on that branch).
        self.assertTrue(_file_on_main(self.temp_dir, "src/x/feature.ts"))
        self.assertTrue(_file_on_main(self.temp_dir, "src/z/feature.ts"))
        self.assertFalse(
            _file_on_main(self.temp_dir, "src/elsewhere/secrets.ts"),
            "scope violator's out-of-scope file must NOT be merged to main",
        )
        # The violator's IN-scope file also didn't land because the whole
        # unit was rejected (not just the out-of-scope file).
        self.assertFalse(
            _file_on_main(self.temp_dir, "src/y/main.ts"),
            "scope violator's in-scope file should also be rejected",
        )

        # Cleanup: merged units' branches/worktrees removed;
        # scope-violator's branch + worktree are preserved for inspection.
        self.assertFalse(
            (worktree_root / "unit_good1").exists(),
            "unit_good1 worktree should be cleaned up after successful merge",
        )
        self.assertFalse(
            (worktree_root / "unit_good2").exists(),
            "unit_good2 worktree should be cleaned up after successful merge",
        )
        self.assertTrue(
            (worktree_root / "unit_bad").exists(),
            "unit_bad worktree should be preserved for operator inspection",
        )
        remaining = _branches_matching(self.temp_dir, f"harness/{self.batch_id}/")
        self.assertEqual(
            remaining,
            [f"harness/{self.batch_id}/unit_bad"],
            "only unit_bad's branch should remain after the batch",
        )


if __name__ == "__main__":
    unittest.main()
