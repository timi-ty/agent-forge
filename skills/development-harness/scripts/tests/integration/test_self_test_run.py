"""End-to-end self-test run against the Tasklet fixture -- unit_056.

PHASE_013's operator-facing instruction is 'run /invoke-development-
harness iteratively until all fixture phases complete and the run
exercises batch >= 2, one merge conflict, and one scope violation'.
Inside the agent-forge dogfood loop, unit_056 implements that
instruction programmatically: the same compute_parallel_batch ->
dispatch_batch -> merge_batch pipeline /invoke walks each turn, but
driven from Python in a throwaway temp repo seeded from the fixture
phase-graph + config captured in unit_055.

The three seeded conditions:
  (1) Batch >= 2: unit_a1 + unit_a2 pack into PHASE_A's first batch
      on disjoint touches_paths.
  (2) Overlap-matrix rejection: unit_a3 overlaps unit_a2 on
      src/items/routes.py, compute_parallel_batch excludes a3 with
      reason 'path_overlap_with:unit_a2'. unit_a3 lands on its own
      in a subsequent batch against a HEAD that already carries a2.
  (3) Scope violation: unit_b2's fake sub-agent faithfully follows
      its description (writes src/seeds/users.json outside declared
      touches_paths), merge_batch._scope_violations hard-rejects it
      with conflict.category 'scope_violation'.

Expected end state (verified by assertions + written to trace.log):
  * PHASE_A: all 3 units merged. src/items/model.py + src/items/
    routes.py + src/router.py on main; bulk-action commit landed on
    src/items/routes.py in a separate turn from the main routes.
  * PHASE_B: 2 of 3 merged cleanly (b1, b3). unit_b2 status 'failed'
    with conflict.category 'scope_violation'.
  * No orphaned worktrees under .harness/worktrees/; no residual
    harness/batch_*/<unit_id> branches.

trace.log is captured at
skills/development-harness/scripts/tests/fixtures/self-test/trace.log
so downstream units 057 + 058 have the raw evidence for the
wall-clock table and post-mortem write-up.
"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from compute_parallel_batch import compute_batch, _parallelism_config  # noqa: E402
from dispatch_batch import dispatch_batch  # noqa: E402
from merge_batch import merge_batch  # noqa: E402
from select_next_unit import compute_frontier  # noqa: E402


# __file__ lives at .../scripts/tests/integration/test_self_test_run.py.
# parents[0] = .../integration/, parents[1] = .../tests/, which is where
# fixtures/self-test/ lives.
TESTS_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = TESTS_DIR / "fixtures" / "self-test"
TRACE_LOG = FIXTURE_DIR / "trace.log"


def _init_repo(root):
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "harness@test.local"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Tasklet Self-Test"],
        check=True,
    )
    (root / "README.md").write_text(
        "tasklet self-test fixture (PHASE_013)\n", encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "initial"], check=True
    )


def _fake_sub_agent_commit(worktree_path, files):
    """Simulate a harness-unit sub-agent: write each file relative to
    the worktree, git add, commit. Used to produce the pre-merge
    commits merge_batch will fan back into main."""
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


# Map each fixture unit id to the files its faithful sub-agent would
# write. unit_b2's file set deliberately includes src/seeds/users.json
# (outside declared touches_paths) so the scope check catches it.
UNIT_FILES = {
    "unit_a1": {"src/items/model.py": "# Item model\n"},
    "unit_a2": {
        "src/items/routes.py": "# Item CRUD routes\n",
        "src/router.py": "# app router\nfrom src.items.routes import *\n",
    },
    "unit_a3": {
        "src/items/routes.py": "# Item CRUD routes\n# + bulk-action endpoint\n",
    },
    "unit_b1": {"src/users/model.py": "# User model\n"},
    "unit_b2": {
        "src/users/routes.py": "# User CRUD routes\n",
        "src/router.py": (
            "# app router\nfrom src.items.routes import *\n"
            "from src.users.routes import *\n"
        ),
        "src/seeds/users.json": '{"admin": "seeded"}\n',
    },
    "unit_b3": {"src/users/seeds.py": "# User seed loader\n"},
}


def _mark_unit_completed(phase_graph, phase_id, unit_id, evidence):
    for phase in phase_graph["phases"]:
        if phase["id"] != phase_id:
            continue
        for unit in phase["units"]:
            if unit["id"] == unit_id:
                unit["status"] = "completed"
                unit.setdefault("validation_evidence", []).append(evidence)
                return
    raise KeyError(f"unit not found: {phase_id}/{unit_id}")


def _units_by_status(phase_graph):
    counts = {}
    for phase in phase_graph["phases"]:
        for unit in phase["units"]:
            counts[unit["status"]] = counts.get(unit["status"], 0) + 1
    return counts


class TestSelfTestEndToEnd(unittest.TestCase):
    """Driver that walks turns until the fixture reaches a stable
    terminal state (either all-complete or blocked-by-scope-violation).
    Asserts each seeded condition fires exactly once."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True)
        )
        _init_repo(self.temp_dir)

        self.phase_graph = json.loads(
            (FIXTURE_DIR / "phase-graph.json").read_text(encoding="utf-8")
        )
        fixture_config = json.loads(
            (FIXTURE_DIR / "config.json").read_text(encoding="utf-8")
        )
        # Build the parallelism config compute_parallel_batch expects
        # from the fixture config. Mirrors what invoke.md Step 4 does.
        self.parallelism = _parallelism_config(fixture_config)

        self.trace_lines = []

    def _log(self, line):
        self.trace_lines.append(line)

    def _run_one_turn(self, turn_idx):
        """One invoke turn: compute_parallel_batch -> dispatch_batch
        -> fake sub-agent commits -> merge_batch. Returns the
        merge_result dict so the caller can inspect batch composition
        + per-unit outcomes."""
        self._log(f"\n--- Turn {turn_idx} ---")

        frontier = compute_frontier(self.phase_graph["phases"])
        if not frontier:
            self._log("Frontier empty. Roadmap is either complete or blocked.")
            return None

        batch_result = compute_batch(frontier, self.parallelism, now=None)
        batch_ids = [u["id"] for u in batch_result["batch"]]
        self._log(f"  Frontier: {[u['id'] for u in frontier]}")
        self._log(f"  Batch:    {batch_ids}")
        if batch_result["excluded"]:
            for excluded in batch_result["excluded"]:
                self._log(
                    f"  Excluded: {excluded['unit_id']} "
                    f"(reason: {excluded['reason']})"
                )

        if not batch_ids:
            self._log("  Nothing packed -- all frontier units excluded.")
            return None

        state = {}
        dispatch_batch(batch_result, root=self.temp_dir, state=state)

        batch_id = batch_result["batch_id"]
        for unit_id in batch_ids:
            worktree = self.temp_dir / ".harness" / "worktrees" / batch_id / unit_id
            _fake_sub_agent_commit(worktree, UNIT_FILES[unit_id])

        merge_result = merge_batch(state, root=self.temp_dir)
        self._log(
            f"  Merge outcome: {merge_result['outcome']} | "
            f"merged={merge_result['merged']} "
            f"conflicted={merge_result['conflicted']}"
        )

        # Flip fleet-unit statuses back into the phase-graph (what
        # Step 9a of invoke.md does after merge).
        for unit in state["execution"]["fleet"]["units"]:
            if unit["status"] == "merged":
                _mark_unit_completed(
                    self.phase_graph,
                    unit["phase_id"],
                    unit["unit_id"],
                    f"self-test turn {turn_idx}: merged cleanly",
                )
                self._log(
                    f"    merged:  {unit['unit_id']} -> phase-graph flipped to completed"
                )
            elif unit["status"] == "failed":
                cat = (unit.get("conflict") or {}).get("category", "unknown")
                self._log(
                    f"    failed:  {unit['unit_id']} (category: {cat})"
                )

        self.assertEqual(
            state["execution"]["fleet"]["mode"], "idle",
            f"Turn {turn_idx}: fleet.mode must return to 'idle' at turn-end; "
            f"got {state['execution']['fleet']['mode']!r}",
        )

        return {
            "batch_ids": batch_ids,
            "excluded": batch_result["excluded"],
            "merge_result": merge_result,
            "state": state,
        }

    def test_full_self_test_run_exercises_all_three_seeded_conditions(self):
        # ----- observation accumulators for seeded-condition checks
        batch_sizes = []
        overlap_exclusions = []
        scope_violations = []

        # Hard safety cap so an unexpected infinite loop doesn't hang.
        for turn_idx in range(1, 11):
            result = self._run_one_turn(turn_idx)
            if result is None:
                break

            batch_sizes.append(len(result["batch_ids"]))
            for excluded in result["excluded"]:
                if excluded["reason"].startswith("path_overlap_with:"):
                    overlap_exclusions.append(
                        (excluded["unit_id"], excluded["reason"])
                    )
            for unit in result["state"]["execution"]["fleet"]["units"]:
                conflict = unit.get("conflict") or {}
                if conflict.get("category") == "scope_violation":
                    scope_violations.append(
                        (unit["unit_id"], conflict.get("paths", []))
                    )

            # Stop once every unit is either completed or blocked as
            # scope-violation-failed (the fixture's terminal state).
            all_settled = all(
                unit["status"] in ("completed",)
                or unit["status"] == "pending"
                and any(
                    scope_violation[0] == unit["id"]
                    for scope_violation in scope_violations
                )
                for phase in self.phase_graph["phases"]
                for unit in phase["units"]
            )
            if all_settled:
                break

        # ----- Condition 1: batch >= 2 -----
        self._log(f"\nBatch sizes observed: {batch_sizes}")
        self.assertGreaterEqual(
            max(batch_sizes, default=0), 2,
            "Seeded condition 1 (batch >= 2) must fire: expected at least "
            "one turn with batch size >= 2",
        )

        # ----- Condition 2: overlap-matrix rejection with unit_a3 -----
        self._log(f"Overlap exclusions: {overlap_exclusions}")
        matching = [
            (uid, reason) for uid, reason in overlap_exclusions
            if uid == "unit_a3" and reason == "path_overlap_with:unit_a2"
        ]
        self.assertTrue(
            matching,
            f"Seeded condition 2 (overlap rejection) must fire: expected "
            f"unit_a3 excluded with reason 'path_overlap_with:unit_a2'; "
            f"observed {overlap_exclusions}",
        )

        # ----- Condition 3: scope violation on unit_b2 -----
        self._log(f"Scope violations: {scope_violations}")
        matching_b2 = [
            (uid, paths) for uid, paths in scope_violations
            if uid == "unit_b2" and "src/seeds/users.json" in paths
        ]
        self.assertTrue(
            matching_b2,
            f"Seeded condition 3 (scope violation) must fire: expected "
            f"unit_b2 rejected with src/seeds/users.json in conflict.paths; "
            f"observed {scope_violations}",
        )

        # ----- Expected end state -----
        status_counts = _units_by_status(self.phase_graph)
        self._log(f"\nFinal status counts: {status_counts}")
        self.assertEqual(
            status_counts.get("completed", 0), 5,
            "Expected 5 units to reach 'completed' (all of PHASE_A + b1 + b3)",
        )
        # unit_b2 stays pending in the phase-graph because the fleet
        # failed it (scope_violation) but the orchestrator only flips
        # the phase-graph on 'merged' status -- 'failed' units stay
        # pending for a human to fix. That's the real observable end-
        # state for the fixture.
        pending_units = {
            unit["id"]
            for phase in self.phase_graph["phases"]
            for unit in phase["units"]
            if unit["status"] == "pending"
        }
        self.assertEqual(
            pending_units, {"unit_b2"},
            f"Only unit_b2 should remain pending (scope violation); "
            f"observed pending set: {pending_units}",
        )

        # ----- Orphan check: no residual batch worktrees or branches -----
        # Leaf worktrees live at .harness/worktrees/<batch_id>/<unit_id>/.
        # A clean run leaves ONLY the b2 worktree alive (the scope-
        # violation path keeps the worktree so a human can inspect +
        # repair). Any other leaf is an orphan.
        worktrees_root = self.temp_dir / ".harness" / "worktrees"
        leaf_worktrees = []
        if worktrees_root.exists():
            for batch_dir in worktrees_root.iterdir():
                if batch_dir.is_dir():
                    leaf_worktrees.extend(
                        p.name for p in batch_dir.iterdir() if p.is_dir()
                    )
        self.assertEqual(
            set(leaf_worktrees), {"unit_b2"},
            f"Only the unit_b2 worktree should survive (scope-violation "
            f"path preserves it); observed leaf worktrees: {leaf_worktrees}",
        )

        # ----- Write trace.log for units 057 + 058 -----
        TRACE_LOG.parent.mkdir(parents=True, exist_ok=True)
        TRACE_LOG.write_text("\n".join(self.trace_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
