"""Tests for the Claude Code continue-loop.py stop hook -- unit 034.

Tests the fleet-mode guard specifically: a previous turn that crashed
mid-batch (fleet.mode in {'dispatched','merging'}) must cause the hook
to exit 0 and delete .invoke-active so the next turn starts cleanly
and the user is pushed toward /sync-development-harness for recovery.

The hook is run as a subprocess with a JSON payload piped to stdin.
Exit codes + .invoke-active presence are the observable contract.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = SKILL_ROOT / "templates" / "claude-code" / "hooks" / "continue-loop.py"


def _run_hook(cwd, stop_hook_active=False):
    """Run continue-loop.py with a minimal Claude Code input payload.

    Returns the CompletedProcess so the caller can assert on returncode
    + stdout + stderr.
    """
    payload = {
        "cwd": str(cwd),
        "stop_hook_active": stop_hook_active,
        "hook_event_name": "Stop",
        "session_id": "test-session",
    }
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def _write_state(root, fleet=None, extras=None):
    """Seed <root>/.harness/state.json with a controllable fleet block.

    If `fleet` is None, the fleet key is omitted entirely (v1 state
    shape). The hook must treat that as idle.
    """
    harness_dir = root / ".harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "schema_version": "2.0",
        "execution": {
            "active_phase": "PHASE_X",
            "active_unit": "unit_x",
            "session_count": 0,
            "loop_budget": 10,
        },
        "checkpoint": {
            "summary": "ready",
            "blockers": [],
            "open_questions": [],
            "next_action": "Complete unit_x",
        },
    }
    if fleet is not None:
        state["execution"]["fleet"] = fleet
    if extras:
        state.update(extras)
    (harness_dir / "state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )


def _touch_invoke_flag(root):
    flag = root / ".harness" / ".invoke-active"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.touch()
    return flag


class ContinueLoopBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True)
        )


class TestFleetModeGuard(ContinueLoopBase):
    """unit_034: fleet.mode != 'idle' must stop the hook and remove the flag."""

    def test_fleet_mode_dispatched_stops_and_removes_flag(self):
        flag = _touch_invoke_flag(self.temp_dir)
        _write_state(
            self.temp_dir,
            fleet={"mode": "dispatched", "batch_id": "batch_x", "units": []},
        )

        result = _run_hook(self.temp_dir)
        self.assertEqual(
            result.returncode, 0,
            f"hook must exit 0 (stop) when fleet.mode=='dispatched'; stderr={result.stderr!r}",
        )
        self.assertFalse(
            flag.exists(),
            ".invoke-active must be removed on fleet-mode stop",
        )

    def test_fleet_mode_merging_stops_and_removes_flag(self):
        flag = _touch_invoke_flag(self.temp_dir)
        _write_state(
            self.temp_dir,
            fleet={"mode": "merging", "batch_id": "batch_x", "units": []},
        )

        result = _run_hook(self.temp_dir)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(flag.exists())

    def test_fleet_mode_idle_passes_the_guard(self):
        """With idle fleet, the guard MUST NOT short-circuit -- the hook
        falls through to the downstream authority chain. Since we don't
        seed phase-graph.json here, the authority chain hits the
        'selector/phase-graph missing' stop at exit 0 with the flag
        removed. The substantive assertion is that the hook DID run the
        downstream logic (evidenced by flag removal via the non-fleet
        stop path), not that it short-circuited on fleet.mode."""
        flag = _touch_invoke_flag(self.temp_dir)
        _write_state(
            self.temp_dir,
            fleet={"mode": "idle", "batch_id": None, "units": []},
        )

        result = _run_hook(self.temp_dir)
        self.assertEqual(result.returncode, 0)
        # Either way (fleet-mode stop or downstream stop) the flag comes
        # off. The meaningful claim is that the guard didn't FALSELY
        # trigger -- we verify that indirectly in a companion test below
        # by seeding every downstream dependency and asserting the hook
        # reaches the block-continue path (exit 2).
        self.assertFalse(flag.exists())

    def test_missing_fleet_block_treated_as_idle(self):
        """v1-style state (no execution.fleet) must not trip the guard."""
        flag = _touch_invoke_flag(self.temp_dir)
        _write_state(self.temp_dir, fleet=None)

        result = _run_hook(self.temp_dir)
        # Same observation as the idle case: exit 0, flag removed via
        # the downstream authority chain (no selector seeded).
        self.assertEqual(result.returncode, 0)
        self.assertFalse(flag.exists())


class TestFleetGuardDoesNotMaskContinuePath(ContinueLoopBase):
    """Positive control: with fleet.mode='idle' AND all downstream
    dependencies wired, the hook reaches the block-continue path
    (exit 2). This proves the fleet-mode guard does not falsely trigger
    on idle state -- the one risk of an overly eager guard."""

    def _seed_full_harness(self, next_unit_id="unit_x"):
        """Create enough harness state that the downstream authority
        chain succeeds: phase-graph.json with a pending unit, a
        select_next_unit.py that returns that unit, checkpoint.next_action
        that contains the unit id."""
        harness_dir = self.temp_dir / ".harness"
        scripts_dir = harness_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # Minimal valid v2 phase-graph.
        phase_graph = {
            "schema_version": "2.0",
            "phases": [
                {
                    "id": "PHASE_X",
                    "slug": "x",
                    "status": "pending",
                    "depends_on": [],
                    "units": [
                        {
                            "id": next_unit_id,
                            "description": "do x",
                            "status": "pending",
                            "depends_on": [],
                            "parallel_safe": False,
                        }
                    ],
                }
            ],
        }
        (harness_dir / "phase-graph.json").write_text(
            json.dumps(phase_graph, indent=2), encoding="utf-8"
        )

        # Tiny stand-in for select_next_unit.py: prints the JSON contract
        # the hook expects. We don't use the real selector here because
        # it imports harness_utils; a one-off script isolates the hook
        # test from selector evolution.
        selector = scripts_dir / "select_next_unit.py"
        selector.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "print(json.dumps({\n"
            f"  'found': True, 'phase_id': 'PHASE_X', 'phase_slug': 'x',\n"
            f"  'unit_id': '{next_unit_id}', 'unit_description': 'do x',\n"
            "  'phase_complete': False, 'all_complete': False\n"
            "}))\n",
            encoding="utf-8",
        )

        # state.json with idle fleet + next_action containing the unit id.
        _write_state(
            self.temp_dir,
            fleet={"mode": "idle", "batch_id": None, "units": []},
            extras=None,
        )
        state_path = harness_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["checkpoint"]["next_action"] = f"Complete {next_unit_id}"
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def test_idle_fleet_with_full_chain_reaches_continue(self):
        self._seed_full_harness(next_unit_id="unit_x")
        flag = _touch_invoke_flag(self.temp_dir)

        result = _run_hook(self.temp_dir, stop_hook_active=False)
        self.assertEqual(
            result.returncode, 2,
            f"hook must exit 2 (continue) when fleet.mode=='idle' and "
            f"the full authority chain passes; stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        self.assertTrue(
            flag.exists(),
            ".invoke-active must be PRESERVED when the hook continues",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload.get("decision"), "block")
        self.assertIn("unit_x", payload.get("reason", ""))


if __name__ == "__main__":
    unittest.main()
