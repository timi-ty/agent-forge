"""Tests for the Cursor continue-loop.py stop hook -- unit 035.

Tests the fleet-mode guard mirrored from the Claude Code variant. A
previous turn that crashed mid-batch (fleet.mode in {'dispatched',
'merging'}) must cause the hook to print `{}` (stop signal under
Cursor's protocol) and delete .invoke-active.

Key protocol difference vs the Claude Code hook: Cursor always exits
0. Stop vs continue is encoded in stdout JSON -- `{}` means stop,
`{"followup_message": "..."}` means continue. Tests inspect stdout
rather than returncode.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = SKILL_ROOT / "templates" / "hooks" / "continue-loop.py"


def _run_hook(workspace_root, status="completed", loop_count=0):
    """Run Cursor's continue-loop.py with a minimal input payload.

    Returns (stdout_json_or_none, stderr, returncode).
    """
    payload = {
        "workspace_roots": [str(workspace_root)],
        "status": status,
        "loop_count": loop_count,
    }
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    try:
        parsed = json.loads(result.stdout) if result.stdout.strip() else None
    except json.JSONDecodeError:
        parsed = None
    return parsed, result.stderr, result.returncode


def _write_state(root, fleet=None, extras=None):
    """Seed <root>/.harness/state.json; fleet=None omits the fleet block."""
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


class CursorHookBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True)
        )


class TestFleetModeGuard(CursorHookBase):
    """unit_035: fleet.mode != 'idle' must stop (print `{}`) and remove the flag."""

    def test_fleet_mode_dispatched_stops_and_removes_flag(self):
        flag = _touch_invoke_flag(self.temp_dir)
        _write_state(
            self.temp_dir,
            fleet={"mode": "dispatched", "batch_id": "batch_x", "units": []},
        )

        parsed, stderr, rc = _run_hook(self.temp_dir)
        self.assertEqual(rc, 0, f"cursor hook always exits 0; stderr={stderr!r}")
        self.assertEqual(
            parsed, {},
            "hook must print `{}` (Cursor stop signal) when fleet.mode=='dispatched'",
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

        parsed, _, rc = _run_hook(self.temp_dir)
        self.assertEqual(rc, 0)
        self.assertEqual(parsed, {})
        self.assertFalse(flag.exists())

    def test_fleet_mode_idle_passes_the_guard(self):
        """Idle fleet must NOT short-circuit the guard -- the hook falls
        through to the downstream authority chain. Without phase-graph
        + selector seeded, the chain hits a stop via the 'selector
        missing' path and prints `{}`. The substantive falsification
        check lives in TestFleetGuardDoesNotMaskContinuePath."""
        flag = _touch_invoke_flag(self.temp_dir)
        _write_state(
            self.temp_dir,
            fleet={"mode": "idle", "batch_id": None, "units": []},
        )

        parsed, _, rc = _run_hook(self.temp_dir)
        self.assertEqual(rc, 0)
        self.assertEqual(parsed, {})
        self.assertFalse(flag.exists())

    def test_missing_fleet_block_treated_as_idle(self):
        """v1-style state (no execution.fleet) must not trip the guard."""
        flag = _touch_invoke_flag(self.temp_dir)
        _write_state(self.temp_dir, fleet=None)

        parsed, _, rc = _run_hook(self.temp_dir)
        self.assertEqual(rc, 0)
        self.assertEqual(parsed, {})
        self.assertFalse(flag.exists())


class TestFleetGuardDoesNotMaskContinuePath(CursorHookBase):
    """Positive control: with fleet.mode='idle' AND all downstream
    dependencies wired, the hook reaches the followup_message continue
    path. Proves the guard doesn't falsely short-circuit on idle."""

    def _seed_full_harness(self, next_unit_id="unit_x"):
        harness_dir = self.temp_dir / ".harness"
        scripts_dir = harness_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

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

        parsed, stderr, rc = _run_hook(
            self.temp_dir, status="completed", loop_count=0
        )
        self.assertEqual(rc, 0)
        self.assertIsNotNone(parsed, f"hook stdout must be JSON; stderr={stderr!r}")
        self.assertIn(
            "followup_message", parsed,
            "hook must print {'followup_message': ...} when authority chain passes",
        )
        self.assertIn("unit_x", parsed["followup_message"])
        self.assertTrue(
            flag.exists(),
            ".invoke-active must be PRESERVED when the hook continues",
        )


if __name__ == "__main__":
    unittest.main()
