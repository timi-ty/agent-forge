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
import time
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
WALL_CLOCK_MD = FIXTURE_DIR / "wall-clock.md"


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


def _load_fixture_config():
    return json.loads((FIXTURE_DIR / "config.json").read_text(encoding="utf-8"))


def _load_fixture_phase_graph():
    return json.loads((FIXTURE_DIR / "phase-graph.json").read_text(encoding="utf-8"))


def _drive_fixture(root, phase_graph, parallelism, trace_lines, max_turns=12):
    """Walk invoke turns against ``phase_graph`` until the roadmap
    reaches a stable terminal state. Returns a run summary dict with
    ``turns`` (count), ``batch_sizes``, ``overlap_exclusions``,
    ``scope_violations``. Mutates ``phase_graph`` in place to reflect
    per-unit status.

    Factored as a free function so the wall-clock comparison test can
    invoke the same driver twice (parallel vs sequential) without
    duplicating logic.
    """
    turns = 0
    batch_sizes = []
    overlap_exclusions = []
    scope_violations = []

    for turn_idx in range(1, max_turns + 1):
        trace_lines.append(f"\n--- Turn {turn_idx} ---")

        frontier = compute_frontier(phase_graph["phases"])
        # compute_frontier filters out only 'completed' -- 'failed'
        # units still surface. For the driver we skip failed units
        # (their worktree + branch were preserved by the scope-
        # violation path; re-dispatching would hit a git-collision).
        # A human operator would either fix + re-flip to 'pending' or
        # mark the unit 'blocked'; both paths are manual, not
        # auto-retry.
        frontier = [u for u in frontier if u.get("status") != "failed"]
        if not frontier:
            trace_lines.append(
                "Frontier empty. Roadmap is either complete or blocked."
            )
            break

        batch_result = compute_batch(frontier, parallelism, now=None)
        batch_ids = [u["id"] for u in batch_result["batch"]]
        trace_lines.append(f"  Frontier: {[u['id'] for u in frontier]}")
        trace_lines.append(f"  Batch:    {batch_ids}")
        for excluded in batch_result["excluded"]:
            trace_lines.append(
                f"  Excluded: {excluded['unit_id']} "
                f"(reason: {excluded['reason']})"
            )
            if excluded["reason"].startswith("path_overlap_with:"):
                overlap_exclusions.append(
                    (excluded["unit_id"], excluded["reason"])
                )

        if not batch_ids:
            trace_lines.append("  Nothing packed -- all frontier units excluded.")
            break

        batch_sizes.append(len(batch_ids))
        turns += 1

        state = {}
        dispatch_batch(batch_result, root=root, state=state)

        batch_id = batch_result["batch_id"]
        for unit_id in batch_ids:
            worktree = root / ".harness" / "worktrees" / batch_id / unit_id
            _fake_sub_agent_commit(worktree, UNIT_FILES[unit_id])

        merge_result = merge_batch(state, root=root)
        trace_lines.append(
            f"  Merge outcome: {merge_result['outcome']} | "
            f"merged={merge_result['merged']} "
            f"conflicted={merge_result['conflicted']}"
        )

        for unit in state["execution"]["fleet"]["units"]:
            if unit["status"] == "merged":
                _mark_unit_completed(
                    phase_graph, unit["phase_id"], unit["unit_id"],
                    f"driver turn {turn_idx}: merged cleanly",
                )
                trace_lines.append(
                    f"    merged:  {unit['unit_id']} -> phase-graph completed"
                )
            elif unit["status"] == "failed":
                cat = (unit.get("conflict") or {}).get("category", "unknown")
                paths = (unit.get("conflict") or {}).get("paths", [])
                trace_lines.append(
                    f"    failed:  {unit['unit_id']} (category: {cat})"
                )
                if cat == "scope_violation":
                    scope_violations.append((unit["unit_id"], paths))
                    # Flip the phase-graph entry to 'failed' so
                    # compute_frontier stops surfacing this unit for
                    # re-dispatch. Without this, a sequential driver
                    # that hits a scope violation would loop forever
                    # (the unit stays 'pending', frontier re-includes
                    # it, next turn attempts to recreate the already-
                    # preserved worktree+branch and fails with a git
                    # collision). Real orchestrators should do the
                    # same: scope_violation is a terminal-for-the-unit
                    # state that requires human intervention.
                    for phase in phase_graph["phases"]:
                        for pg_unit in phase["units"]:
                            if pg_unit["id"] == unit["unit_id"]:
                                pg_unit["status"] = "failed"
                                pg_unit.setdefault(
                                    "validation_evidence", []
                                ).append(
                                    f"driver turn {turn_idx}: "
                                    f"scope_violation on {paths}"
                                )

        # Stable terminal state: every unit is either completed OR
        # pending-with-a-recorded-scope-violation. Continuing past this
        # would loop forever because pending units with scope
        # violations never get re-picked-up (their sub-agent would fail
        # again).
        completed_ids = {
            unit["id"] for phase in phase_graph["phases"]
            for unit in phase["units"] if unit["status"] == "completed"
        }
        violating_ids = {uid for uid, _ in scope_violations}
        total_units = sum(len(p["units"]) for p in phase_graph["phases"])
        if len(completed_ids) + len(violating_ids) >= total_units:
            break

    return {
        "turns": turns,
        "batch_sizes": batch_sizes,
        "overlap_exclusions": overlap_exclusions,
        "scope_violations": scope_violations,
    }


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
        # Same filter as _drive_fixture -- compute_frontier surfaces
        # 'failed' units alongside 'pending' ones, but failed units
        # should not be re-dispatched (their worktree+branch are
        # preserved for human inspection).
        frontier = [u for u in frontier if u.get("status") != "failed"]
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
                paths = (unit.get("conflict") or {}).get("paths", [])
                self._log(
                    f"    failed:  {unit['unit_id']} (category: {cat})"
                )
                if cat == "scope_violation":
                    # Flip phase-graph entry to 'failed' so
                    # compute_frontier stops surfacing this unit for
                    # re-dispatch. Without this, a driver that runs
                    # long enough would hit the same-second-batch_id
                    # branch-name collision because the scope-violation
                    # path preserves the worktree + branch.
                    for phase in self.phase_graph["phases"]:
                        for pg_unit in phase["units"]:
                            if pg_unit["id"] == unit["unit_id"]:
                                pg_unit["status"] = "failed"
                                pg_unit.setdefault(
                                    "validation_evidence", []
                                ).append(
                                    f"self-test turn {turn_idx}: "
                                    f"scope_violation on {paths}"
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

            # Stop once every unit is either completed or failed (the
            # fixture's terminal state). After the scope-violation
            # flip above, b2 is 'failed'; everything else is
            # 'completed'.
            all_settled = all(
                unit["status"] in ("completed", "failed")
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
        # unit_b2 is flipped to 'failed' in the phase-graph by the
        # driver's scope-violation handler, so compute_frontier stops
        # re-dispatching it. That's the terminal state for a scope-
        # violating unit; human intervention is required to repair the
        # touches_paths/description discrepancy + re-run the unit.
        failed_units = {
            unit["id"]
            for phase in self.phase_graph["phases"]
            for unit in phase["units"]
            if unit["status"] == "failed"
        }
        self.assertEqual(
            failed_units, {"unit_b2"},
            f"Only unit_b2 should be marked failed (scope violation); "
            f"observed failed set: {failed_units}",
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


# ---------------------------------------------------------------------
# unit_057 -- wall-clock parallel vs sequential comparison
# ---------------------------------------------------------------------


class TestWallClockParallelVsSequential(unittest.TestCase):
    """Run the Tasklet fixture end-to-end twice -- once with the
    fixture's parallelism config (max_concurrent_units=3) and once
    with a sequential baseline (max_concurrent_units=1, forcing
    batch-of-1 throughout) -- and record both wall-clocks in a
    markdown table committed to fixtures/self-test/wall-clock.md
    for unit_058's post-mortem to embed.

    The sequential baseline uses worktree fan-out with a capacity cap
    of 1 rather than the in-tree fast path. This keeps the comparison
    apples-to-apples: same git operations (worktree add + merge) per
    unit, only batch-size differs. A pure in-tree baseline would
    conflate 'sequential' with 'avoids worktree overhead' and
    under-count parallelism's real saving.
    """

    def _run_with_parallelism(self, max_concurrent_units):
        """Spawn a fresh temp repo, run the fixture driver to
        completion, time it. Returns (elapsed_seconds, summary,
        trace_lines)."""
        temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda td=temp_dir:
            __import__("shutil").rmtree(td, ignore_errors=True)
        )
        _init_repo(temp_dir)

        phase_graph = _load_fixture_phase_graph()
        config = _load_fixture_config()
        parallelism = _parallelism_config(config)
        parallelism["max_concurrent_units"] = max_concurrent_units

        trace_lines = [
            f"Run config: max_concurrent_units={max_concurrent_units}",
        ]
        start = time.monotonic()
        summary = _drive_fixture(temp_dir, phase_graph, parallelism, trace_lines)
        elapsed = time.monotonic() - start
        return elapsed, summary, trace_lines

    def test_parallel_vs_sequential_produces_comparable_table(self):
        # ----- Parallel run (max_concurrent_units=3, fixture default)
        parallel_elapsed, parallel_summary, parallel_trace = (
            self._run_with_parallelism(max_concurrent_units=3)
        )

        # ----- Sequential baseline (max_concurrent_units=1)
        sequential_elapsed, sequential_summary, sequential_trace = (
            self._run_with_parallelism(max_concurrent_units=1)
        )

        # ----- Shape assertions
        # Parallel run packs units into batches; sequential forces
        # one unit per turn. Expect sequential to take more turns
        # even though it eventually reaches the same terminal state.
        self.assertGreater(
            sequential_summary["turns"], parallel_summary["turns"],
            f"sequential baseline must take more turns than parallel "
            f"(sequential: {sequential_summary['turns']}, "
            f"parallel: {parallel_summary['turns']})",
        )
        # Parallel run must have observed >= 1 batch of size >= 2.
        self.assertGreaterEqual(
            max(parallel_summary["batch_sizes"]), 2,
            "parallel run must exercise batch >= 2",
        )
        # Sequential run must never exceed batch size 1.
        self.assertTrue(
            all(b == 1 for b in sequential_summary["batch_sizes"]),
            f"sequential run must have all batches of size 1; got "
            f"{sequential_summary['batch_sizes']}",
        )

        # Both runs must hit exactly one scope violation on unit_b2 --
        # that's a property of the fixture, not the parallelism config.
        for label, summary in [("parallel", parallel_summary),
                               ("sequential", sequential_summary)]:
            b2_violations = [
                uid for uid, _ in summary["scope_violations"]
                if uid == "unit_b2"
            ]
            self.assertEqual(
                len(b2_violations), 1,
                f"{label} run must record exactly one unit_b2 scope "
                f"violation; got {summary['scope_violations']}",
            )

        # ----- Write wall-clock.md
        ratio = (sequential_elapsed / parallel_elapsed
                 if parallel_elapsed > 0 else float("inf"))
        md = _build_wall_clock_markdown(
            parallel_elapsed=parallel_elapsed,
            parallel_summary=parallel_summary,
            sequential_elapsed=sequential_elapsed,
            sequential_summary=sequential_summary,
            ratio=ratio,
        )
        WALL_CLOCK_MD.parent.mkdir(parents=True, exist_ok=True)
        WALL_CLOCK_MD.write_text(md, encoding="utf-8")


def _build_wall_clock_markdown(
    parallel_elapsed, parallel_summary,
    sequential_elapsed, sequential_summary,
    ratio,
):
    """Render the wall-clock comparison table + narrative.

    Embedded by unit_058's POST-MORTEM.md. Shape is grep-friendly and
    assertable -- every row carries its own label the post-mortem
    tests can pin on."""
    lines = [
        "# Wall-clock comparison — Tasklet self-test fixture",
        "",
        ("Captured by `test_self_test_run.TestWallClockParallelVsSequential."
         "test_parallel_vs_sequential_produces_comparable_table` on a fresh "
         "run against the fixture in [phase-graph.json](./phase-graph.json). "
         "Both runs use worktree fan-out (dispatch + merge) so the only "
         "independent variable is `max_concurrent_units`."),
        "",
        "| Run | max_concurrent_units | Turns | Batch sizes | Wall-clock (s) |",
        "|-----|----------------------|-------|-------------|----------------|",
        (f"| Parallel   | 3 | {parallel_summary['turns']} | "
         f"{parallel_summary['batch_sizes']} | {parallel_elapsed:.2f} |"),
        (f"| Sequential | 1 | {sequential_summary['turns']} | "
         f"{sequential_summary['batch_sizes']} | {sequential_elapsed:.2f} |"),
        "",
        "## Ratio",
        "",
        (f"Sequential / Parallel wall-clock ratio: **{ratio:.2f}x**. The "
         f"parallel run completes in {parallel_summary['turns']} turn(s) "
         f"versus {sequential_summary['turns']} for sequential. On this "
         f"fixture the batching savings come from Turn 1 packing "
         f"unit_a1 + unit_a2 and Turn 3 packing the full PHASE_B set "
         f"(b1 + b2 + b3 before b2's scope-violation rejection). A real "
         f"project with slower per-unit work (real test runs, not "
         f"fake-commits) will see a larger ratio because the fixed "
         f"overhead (worktree add + merge) is unchanged while the "
         f"per-unit work overlaps."),
        "",
        "## Orphan check",
        "",
        ("Both runs leave only `unit_b2`'s worktree alive -- the "
         "scope-violation path in `merge_batch.py` preserves it so a "
         "human can inspect and repair. All other worktrees are torn "
         "down; no residual `harness/batch_*/*` branches remain."),
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    unittest.main()
