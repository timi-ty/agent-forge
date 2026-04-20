"""Tests for the Claude Code continue-loop.py stop hook.

Originally unit_034 tested the fleet-mode guard in the block-continue
driver. PHASE_011 unit_bugfix_002 (ISSUE_002) retired that role: the
Claude Code hook is now a precondition-only checker that ALWAYS exits
0 and prints a one-line advisory ('proceed: unit_x in PHASE_X' or
'stop: <reason>'). Autonomous multi-turn runs use /loop. See
references/claude-code-continuation.md for the full reasoning.

These tests track the new contract:
  * exit code is always 0 (never 2)
  * stdout carries the advisory
  * .invoke-active is cleaned up on every path (including the
    proceed path) because /loop will recreate it on the next firing

The hook is run as a subprocess with a JSON payload piped to stdin.
Exit codes + stdout advisories + .invoke-active presence are the
observable contract.
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
    """fleet.mode != 'idle' must surface as a 'stop: fleet.mode is ...'
    advisory. The hook always exits 0; the advisory distinguishes the
    reason."""

    def test_fleet_mode_dispatched_emits_stop_advisory(self):
        flag = _touch_invoke_flag(self.temp_dir)
        _write_state(
            self.temp_dir,
            fleet={"mode": "dispatched", "batch_id": "batch_x", "units": []},
        )

        result = _run_hook(self.temp_dir)
        self.assertEqual(
            result.returncode, 0,
            f"hook must always exit 0; stderr={result.stderr!r}",
        )
        self.assertIn(
            "stop: fleet.mode is 'dispatched'", result.stdout,
            f"advisory must name the non-idle fleet.mode; stdout={result.stdout!r}",
        )
        self.assertFalse(
            flag.exists(),
            ".invoke-active must be removed after every precondition path",
        )

    def test_fleet_mode_merging_emits_stop_advisory(self):
        flag = _touch_invoke_flag(self.temp_dir)
        _write_state(
            self.temp_dir,
            fleet={"mode": "merging", "batch_id": "batch_x", "units": []},
        )

        result = _run_hook(self.temp_dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("stop: fleet.mode is 'merging'", result.stdout)
        self.assertFalse(flag.exists())

    def test_fleet_mode_idle_passes_the_guard(self):
        """With idle fleet and no downstream dependencies seeded, the
        authority chain hits 'selector/phase-graph missing' and emits
        that advisory -- NOT the fleet-mode advisory. Proves the guard
        didn't falsely short-circuit on idle state."""
        flag = _touch_invoke_flag(self.temp_dir)
        _write_state(
            self.temp_dir,
            fleet={"mode": "idle", "batch_id": None, "units": []},
        )

        result = _run_hook(self.temp_dir)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("fleet.mode", result.stdout,
                         f"idle fleet must not produce a fleet advisory; stdout={result.stdout!r}")
        self.assertIn("stop: select_next_unit.py or phase-graph.json missing",
                      result.stdout)
        self.assertFalse(flag.exists())

    def test_missing_fleet_block_treated_as_idle(self):
        """v1-style state (no execution.fleet) must behave as idle."""
        flag = _touch_invoke_flag(self.temp_dir)
        _write_state(self.temp_dir, fleet=None)

        result = _run_hook(self.temp_dir)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("fleet.mode", result.stdout)
        self.assertFalse(flag.exists())


class TestPreconditionCheckerReachesProceed(ContinueLoopBase):
    """Positive control: with fleet.mode='idle' AND all downstream
    dependencies wired, the hook reaches the 'proceed: <unit> in <phase>'
    advisory. Still exits 0. Still cleans up .invoke-active. Multi-turn
    autonomy happens via /loop, which recreates the flag on each firing."""

    def _seed_full_harness(self, next_unit_id="unit_x"):
        """Create enough harness state that the authority chain succeeds."""
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

        # Tiny stand-in for select_next_unit.py: prints the JSON contract
        # the hook expects.
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
        )
        state_path = harness_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["checkpoint"]["next_action"] = f"Complete {next_unit_id}"
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def test_idle_fleet_with_full_chain_emits_proceed_advisory(self):
        self._seed_full_harness(next_unit_id="unit_x")
        flag = _touch_invoke_flag(self.temp_dir)

        result = _run_hook(self.temp_dir, stop_hook_active=False)
        self.assertEqual(
            result.returncode, 0,
            f"hook must always exit 0 (no more exit-2 block-continue); "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "proceed: unit_x in PHASE_X", result.stdout,
            "advisory must name the next unit + phase when preconditions pass",
        )
        self.assertFalse(
            flag.exists(),
            ".invoke-active must be cleaned up on every path; /loop will "
            "recreate it on the next firing",
        )

    def test_stop_hook_active_is_ignored_in_precondition_mode(self):
        """Pre-fix, stop_hook_active=True was the one-shot guard that
        short-circuited the hook. In the new precondition-only mode it
        is irrelevant -- we never force-continue, so the guard has
        nothing to guard against."""
        self._seed_full_harness(next_unit_id="unit_x")
        _touch_invoke_flag(self.temp_dir)

        result = _run_hook(self.temp_dir, stop_hook_active=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("proceed: unit_x in PHASE_X", result.stdout)


class TestFlagAbsentIsNoop(ContinueLoopBase):
    """When .invoke-active is not present, the hook must exit 0 with
    no advisory output. It is a no-op outside harness invoke sessions."""

    def test_no_invoke_flag_silent_noop(self):
        result = _run_hook(self.temp_dir)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout, "",
            "flag-absent path must not emit advisories",
        )


class TestNonIdleBudgetAndBlockers(ContinueLoopBase):
    """Coverage for the remaining authority-chain stop paths."""

    def test_loop_budget_exhausted_emits_stop_advisory(self):
        _touch_invoke_flag(self.temp_dir)
        _write_state(
            self.temp_dir,
            fleet={"mode": "idle", "batch_id": None, "units": []},
        )
        state_path = self.temp_dir / ".harness" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["execution"]["session_count"] = 12
        state["execution"]["loop_budget"] = 10
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

        result = _run_hook(self.temp_dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("stop: loop_budget exhausted (12/10)", result.stdout)

    def test_blockers_non_empty_emits_stop_advisory(self):
        _touch_invoke_flag(self.temp_dir)
        _write_state(
            self.temp_dir,
            fleet={"mode": "idle", "batch_id": None, "units": []},
        )
        state_path = self.temp_dir / ".harness" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["checkpoint"]["blockers"] = ["something went wrong"]
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

        result = _run_hook(self.temp_dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("stop: checkpoint.blockers is non-empty", result.stdout)


if __name__ == "__main__":
    unittest.main()
