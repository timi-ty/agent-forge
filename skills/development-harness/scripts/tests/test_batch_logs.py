"""Tests for per-batch log artifacts -- unit 043.

Every parallel turn should leave a .harness/logs/<batch_id>/ directory
with:
  * batch.json -- the batch plan + dispatched fleet (written by
    dispatch_batch at dispatch time).
  * merge.log  -- grep-friendly merge summary (written by merge_batch
    at the end of every non-empty flow, including aborted + validation-
    failed paths).
  * validation.log -- post-merge validator message (written by
    merge_batch whenever the validator runs, regardless of outcome).
  * <unit_id>.md   -- sub-agent summary (owned by the sub-agent, per
    the harness-unit contract; the orchestrator must NOT fabricate one).

Log writes are best-effort and must never block a successful dispatch
or merge. These tests pin both the happy-path artifact presence and
the non-blocking guarantee (PermissionError on mkdir does not raise).
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from compute_parallel_batch import compute_batch  # noqa: E402
from dispatch_batch import _write_batch_log as _dispatch_write_log  # noqa: E402
from dispatch_batch import dispatch_batch  # noqa: E402
from merge_batch import (  # noqa: E402
    _write_batch_log as _merge_write_log,
    merge_batch,
)
from select_next_unit import compute_frontier  # noqa: E402


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


def _parallel_config(enabled=True):
    return {
        "enabled": enabled,
        "max_concurrent_units": 3,
        "conflict_strategy": "abort_batch",
        "require_touches_paths": True,
        "allow_cross_phase": False,
    }


def _phase_graph_two_units():
    return {
        "schema_version": "2.0",
        "phases": [
            {
                "id": "PHASE_LOG",
                "slug": "log-fixture",
                "status": "pending",
                "depends_on": [],
                "units": [
                    {
                        "id": "unit_alpha", "description": "touch src/alpha",
                        "status": "pending", "depends_on": [],
                        "parallel_safe": True, "touches_paths": ["src/alpha/**"],
                    },
                    {
                        "id": "unit_beta", "description": "touch src/beta",
                        "status": "pending", "depends_on": [],
                        "parallel_safe": True, "touches_paths": ["src/beta/**"],
                    },
                ],
            }
        ],
    }


def _fake_agent_commit(worktree_path, files):
    for rel, body in files.items():
        target = Path(worktree_path) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(worktree_path), "add", rel], check=True
        )
    subprocess.run(
        ["git", "-C", str(worktree_path), "commit", "-q", "-m", "sub-agent work"],
        check=True,
    )


class BatchLogsBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True)
        )
        _init_repo(self.temp_dir)

    def _logs_dir(self, batch_id):
        return self.temp_dir / ".harness" / "logs" / batch_id


class TestDispatchWritesBatchJson(BatchLogsBase):
    def test_dispatch_produces_batch_json(self):
        phase_graph = _phase_graph_two_units()
        frontier = compute_frontier(phase_graph["phases"])
        batch_result = compute_batch(frontier, _parallel_config(True), now=None)
        batch_id = batch_result["batch_id"]

        state = {}
        dispatch_batch(batch_result, root=self.temp_dir, state=state)

        batch_json = self._logs_dir(batch_id) / "batch.json"
        self.assertTrue(batch_json.exists(),
                        f"dispatch must write {batch_json}")
        data = json.loads(batch_json.read_text(encoding="utf-8"))
        self.assertEqual(data["batch_id"], batch_id)
        self.assertIn("dispatched_at", data)
        self.assertIn("batch_plan", data)
        self.assertIn("fleet", data)
        self.assertEqual(data["fleet"]["mode"], "dispatched")
        self.assertEqual(
            sorted(u["unit_id"] for u in data["fleet"]["units"]),
            ["unit_alpha", "unit_beta"],
        )


class TestMergeWritesMergeAndValidationLogs(BatchLogsBase):
    def test_happy_path_produces_merge_and_validation_logs(self):
        phase_graph = _phase_graph_two_units()
        frontier = compute_frontier(phase_graph["phases"])
        batch_result = compute_batch(frontier, _parallel_config(True), now=None)
        batch_id = batch_result["batch_id"]

        state = {}
        dispatch_batch(batch_result, root=self.temp_dir, state=state)

        for uid, slice_ in [("unit_alpha", "alpha"), ("unit_beta", "beta")]:
            wt = self.temp_dir / ".harness" / "worktrees" / batch_id / uid
            _fake_agent_commit(wt, {f"src/{slice_}/main.ts": f"// {uid}\n"})

        # Custom validator so validation.log has a predictable body.
        def validator(root, merged_unit_ids):
            return True, f"validator ran on {len(merged_unit_ids)} unit(s)"

        merge_batch(
            state, root=self.temp_dir,
            run_post_merge_validation=validator,
        )

        merge_log = self._logs_dir(batch_id) / "merge.log"
        validation_log = self._logs_dir(batch_id) / "validation.log"

        self.assertTrue(merge_log.exists(), f"merge.log missing at {merge_log}")
        self.assertTrue(validation_log.exists(),
                        f"validation.log missing at {validation_log}")

        merge_body = merge_log.read_text(encoding="utf-8")
        self.assertIn(f"batch_id: {batch_id}", merge_body)
        self.assertIn("outcome: ok", merge_body)
        # The merged block must list both units (grep-friendly shape).
        self.assertIn("merged (2):", merge_body)
        self.assertIn("- unit_alpha", merge_body)
        self.assertIn("- unit_beta", merge_body)

        val_body = validation_log.read_text(encoding="utf-8")
        self.assertIn("validator_ok: True", val_body)
        self.assertIn("validator ran on 2 unit(s)", val_body)

    def test_validation_failure_still_writes_both_logs(self):
        """Even when post-merge validation rejects the merges and we
        rollback via git reset --hard, both log files must exist so a
        human can reconstruct what happened."""
        phase_graph = _phase_graph_two_units()
        frontier = compute_frontier(phase_graph["phases"])
        batch_result = compute_batch(frontier, _parallel_config(True), now=None)
        batch_id = batch_result["batch_id"]

        state = {}
        dispatch_batch(batch_result, root=self.temp_dir, state=state)

        for uid, slice_ in [("unit_alpha", "alpha"), ("unit_beta", "beta")]:
            wt = self.temp_dir / ".harness" / "worktrees" / batch_id / uid
            _fake_agent_commit(wt, {f"src/{slice_}/main.ts": f"// {uid}\n"})

        def failing_validator(root, merged_unit_ids):
            return False, "post-merge typecheck failed: 3 errors"

        result = merge_batch(
            state, root=self.temp_dir,
            run_post_merge_validation=failing_validator,
        )
        self.assertEqual(result["outcome"], "validation_failed")

        merge_log = self._logs_dir(batch_id) / "merge.log"
        validation_log = self._logs_dir(batch_id) / "validation.log"
        self.assertTrue(merge_log.exists())
        self.assertTrue(validation_log.exists())

        self.assertIn("outcome: validation_failed",
                      merge_log.read_text(encoding="utf-8"))
        val_body = validation_log.read_text(encoding="utf-8")
        self.assertIn("validator_ok: False", val_body)
        self.assertIn("post-merge typecheck failed", val_body)

    def test_empty_fleet_writes_no_log(self):
        """No batch, no log. The empty-fleet short-circuit must not
        create a .harness/logs/ tree -- it would be a lie (nothing ran
        to log)."""
        state = {
            "execution": {
                "fleet": {"mode": "dispatched", "batch_id": None, "units": []}
            }
        }
        merge_batch(state, root=self.temp_dir)
        logs_root = self.temp_dir / ".harness" / "logs"
        self.assertFalse(logs_root.exists(),
                         "empty-fleet merge must not create .harness/logs/")


class TestLogWritesAreBestEffort(BatchLogsBase):
    """Both _write_batch_log helpers must never raise: a missing or
    unwritable log dir is a reportability miss, not a correctness
    failure. Regression guard so log writes don't accidentally become
    load-bearing."""

    def test_merge_write_batch_log_returns_false_on_missing_batch_id(self):
        """The merge helper's empty-batch_id early-return. The dispatch
        helper has no such guard by design (dispatch always computes
        batch_id from batch_result and errors earlier if it is missing)."""
        self.assertFalse(_merge_write_log(self.temp_dir, "", "merge.log", "x"))
        self.assertFalse(_merge_write_log(self.temp_dir, None, "merge.log", "x"))

    def test_write_batch_log_swallows_oserror(self):
        """Point LOGS_DIR at a read-only parent so mkdir raises OSError.
        The helper must catch and return False."""
        if os.name == "nt":
            self.skipTest(
                "Windows chmod-readonly semantics differ; equivalent coverage "
                "lives in the empty-batch_id path and the happy-path tests."
            )
        blocked = self.temp_dir / "blocked"
        blocked.mkdir()
        os.chmod(blocked, stat.S_IREAD | stat.S_IEXEC)
        try:
            # Call the dispatch helper pointed at the read-only dir as
            # if it were the harness root.
            ok = _dispatch_write_log(blocked, "batch_x", "batch.json", {"x": 1})
            self.assertFalse(ok, "helper must swallow OSError and return False")
        finally:
            os.chmod(blocked, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

    def test_dispatch_succeeds_even_if_log_write_fails(self):
        """Replace the helper with one that always raises, and confirm
        dispatch_batch still completes and flips fleet.mode to
        dispatched. Proves the log write is not load-bearing for the
        orchestrator's critical path."""
        import dispatch_batch as dispatch_mod

        def always_fail(root, batch_id, filename, content):
            raise OSError("simulated log-write failure")

        original = dispatch_mod._write_batch_log
        dispatch_mod._write_batch_log = always_fail
        try:
            phase_graph = _phase_graph_two_units()
            frontier = compute_frontier(phase_graph["phases"])
            batch_result = compute_batch(frontier, _parallel_config(True), now=None)

            state = {}
            # The helper raising would bubble through if the call site
            # doesn't treat it as best-effort. Today the helper itself
            # catches OSError, but this monkeypatch exposes the call-
            # site guarantee: even if the helper raises, dispatch must
            # not fail.
            try:
                dispatch_batch(batch_result, root=self.temp_dir, state=state)
            except OSError:
                self.fail(
                    "dispatch_batch must not propagate log-write OSError; "
                    "the log write is best-effort"
                )
        finally:
            dispatch_mod._write_batch_log = original

        self.assertEqual(state["execution"]["fleet"]["mode"], "dispatched")


if __name__ == "__main__":
    unittest.main()
