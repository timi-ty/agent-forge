"""Tests for safety_rails.py -- unit 037.

Covers the session-scoped kill switch: record_failure keeps a JSONL
log of failures, trips .harness/.parallel-disabled after two
scope_violation/ambiguity failures, is idempotent past the threshold,
ignores failures in other categories, and clear_safety_rails removes
both files.

Also exercises the CLI and the hook's inline clear-on-stop behavior
(both Claude Code and Cursor hooks wipe the safety-rail files inside
their _stop() helpers so the next session starts clean).
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from safety_rails import (  # noqa: E402
    COUNTED_CATEGORIES,
    KILL_SWITCH_THRESHOLD,
    clear_safety_rails,
    is_parallel_disabled,
    record_failure,
)

SAFETY_RAILS_SCRIPT = SCRIPT_DIR / "safety_rails.py"
SKILL_ROOT = SCRIPT_DIR.parent
CLAUDE_HOOK = SKILL_ROOT / "templates" / "claude-code" / "hooks" / "continue-loop.py"
CURSOR_HOOK = SKILL_ROOT / "templates" / "hooks" / "continue-loop.py"


class SafetyRailsBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True)
        )
        (self.temp_dir / ".harness").mkdir()

    def _kill_switch(self):
        return self.temp_dir / ".harness" / ".parallel-disabled"

    def _failures_log(self):
        return self.temp_dir / ".harness" / ".parallel-failures.jsonl"


class TestRecordFailureThreshold(SafetyRailsBase):
    def test_single_failure_below_threshold_does_not_trip(self):
        tripped = record_failure(self.temp_dir, "scope_violation", unit_id="u1")
        self.assertFalse(tripped)
        self.assertFalse(self._kill_switch().exists())
        self.assertTrue(self._failures_log().exists())

    def test_two_failures_trip_kill_switch(self):
        self.assertFalse(record_failure(self.temp_dir, "scope_violation", unit_id="u1"))
        tripped = record_failure(self.temp_dir, "scope_violation", unit_id="u2")
        self.assertTrue(tripped, "second scope_violation must trip the kill switch")
        self.assertTrue(self._kill_switch().exists())

        body = json.loads(self._kill_switch().read_text(encoding="utf-8"))
        self.assertEqual(body["count"], 2)
        self.assertIn("scope_violation/ambiguity", body["reason"])

    def test_ambiguity_and_scope_violation_mix_count_together(self):
        record_failure(self.temp_dir, "scope_violation", unit_id="u1")
        tripped = record_failure(self.temp_dir, "ambiguity", unit_id="u2")
        self.assertTrue(tripped)
        self.assertTrue(self._kill_switch().exists())

    def test_third_failure_does_not_re_trip(self):
        record_failure(self.temp_dir, "scope_violation", unit_id="u1")
        self.assertTrue(record_failure(self.temp_dir, "scope_violation", unit_id="u2"))
        tripped_again = record_failure(self.temp_dir, "scope_violation", unit_id="u3")
        self.assertFalse(
            tripped_again,
            "record_failure must return False once the kill switch is already tripped",
        )
        self.assertTrue(self._kill_switch().exists())

    def test_non_counted_categories_do_not_count(self):
        # Log four 'infrastructure' failures -- well above threshold --
        # but none count toward the kill switch.
        for i in range(4):
            tripped = record_failure(
                self.temp_dir, "infrastructure", unit_id=f"u{i}"
            )
            self.assertFalse(tripped)
        self.assertFalse(self._kill_switch().exists())
        # The failure log still records them, for observability.
        with open(self._failures_log(), "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
        self.assertEqual(len(lines), 4)

    def test_other_categories_do_not_pollute_counted_total(self):
        record_failure(self.temp_dir, "scope_violation", unit_id="u1")
        record_failure(self.temp_dir, "infrastructure", unit_id="u2")
        record_failure(self.temp_dir, "validation", unit_id="u3")
        # Still only one COUNTED failure; kill switch must not be tripped.
        self.assertFalse(self._kill_switch().exists())
        tripped = record_failure(self.temp_dir, "ambiguity", unit_id="u4")
        self.assertTrue(tripped, "second counted failure (ambiguity) must trip")


class TestHelpers(SafetyRailsBase):
    def test_is_parallel_disabled_reflects_file(self):
        self.assertFalse(is_parallel_disabled(self.temp_dir))
        self._kill_switch().write_text("{}", encoding="utf-8")
        self.assertTrue(is_parallel_disabled(self.temp_dir))

    def test_clear_removes_both_files(self):
        self._kill_switch().write_text("{}", encoding="utf-8")
        self._failures_log().write_text(
            json.dumps({"category": "scope_violation"}) + "\n",
            encoding="utf-8",
        )
        clear_safety_rails(self.temp_dir)
        self.assertFalse(self._kill_switch().exists())
        self.assertFalse(self._failures_log().exists())

    def test_clear_is_idempotent(self):
        # Missing files -- clear must not raise.
        clear_safety_rails(self.temp_dir)
        clear_safety_rails(self.temp_dir)
        self.assertFalse(self._kill_switch().exists())


class TestCliSmoke(SafetyRailsBase):
    def test_cli_record_then_status(self):
        subprocess.run(
            [
                sys.executable, str(SAFETY_RAILS_SCRIPT), "record",
                "--category", "scope_violation",
                "--unit-id", "u1",
                "--root", str(self.temp_dir),
            ],
            check=True, capture_output=True, text=True,
        )

        result = subprocess.run(
            [sys.executable, str(SAFETY_RAILS_SCRIPT), "status", "--root", str(self.temp_dir)],
            check=True, capture_output=True, text=True,
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["parallel_disabled"])
        self.assertEqual(payload["session_failure_count"], 1)

        # Second failure trips the switch.
        subprocess.run(
            [
                sys.executable, str(SAFETY_RAILS_SCRIPT), "record",
                "--category", "ambiguity",
                "--unit-id", "u2",
                "--root", str(self.temp_dir),
            ],
            check=True, capture_output=True, text=True,
        )
        result = subprocess.run(
            [sys.executable, str(SAFETY_RAILS_SCRIPT), "status", "--root", str(self.temp_dir)],
            check=True, capture_output=True, text=True,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["parallel_disabled"])
        self.assertEqual(payload["session_failure_count"], 2)

    def test_cli_clear(self):
        record_failure(self.temp_dir, "scope_violation", unit_id="u1")
        record_failure(self.temp_dir, "scope_violation", unit_id="u2")
        self.assertTrue(is_parallel_disabled(self.temp_dir))

        subprocess.run(
            [sys.executable, str(SAFETY_RAILS_SCRIPT), "clear", "--root", str(self.temp_dir)],
            check=True, capture_output=True, text=True,
        )
        self.assertFalse(is_parallel_disabled(self.temp_dir))
        self.assertFalse(self._failures_log().exists())


class TestHookStopClearsSafetyRails(SafetyRailsBase):
    """Both hooks' _stop() must wipe .parallel-disabled + failure log,
    not just .invoke-active. Exercised via subprocess with controlled
    stdin so we don't depend on the full hook authority chain."""

    def _write_minimal_state(self, fleet_mode="dispatched"):
        """Seed a state that forces the hook's fleet-mode guard to fire,
        so the hook calls _stop() and exits. We want to observe the
        cleanup side-effects of _stop, not the authority chain."""
        state = {
            "schema_version": "2.0",
            "execution": {
                "active_phase": "PHASE_X",
                "session_count": 0,
                "loop_budget": 10,
                "fleet": {"mode": fleet_mode, "batch_id": "batch_x", "units": []},
            },
            "checkpoint": {
                "summary": "ready",
                "blockers": [],
                "open_questions": [],
                "next_action": "Complete unit_x",
            },
        }
        (self.temp_dir / ".harness" / "state.json").write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )

    def _seed_safety_rails_state(self):
        (self.temp_dir / ".harness" / ".invoke-active").touch()
        self._kill_switch().write_text(
            json.dumps({"reason": "test", "count": 2}), encoding="utf-8"
        )
        self._failures_log().write_text(
            json.dumps({"category": "scope_violation"}) + "\n",
            encoding="utf-8",
        )

    def test_claude_code_hook_stop_clears_safety_rails(self):
        self._seed_safety_rails_state()
        self._write_minimal_state(fleet_mode="dispatched")

        payload = json.dumps({
            "cwd": str(self.temp_dir),
            "stop_hook_active": False,
            "hook_event_name": "Stop",
            "session_id": "test-session",
        })
        result = subprocess.run(
            [sys.executable, str(CLAUDE_HOOK)],
            input=payload, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
        self.assertFalse((self.temp_dir / ".harness" / ".invoke-active").exists())
        self.assertFalse(
            self._kill_switch().exists(),
            "Claude Code hook _stop() must remove .parallel-disabled",
        )
        self.assertFalse(
            self._failures_log().exists(),
            "Claude Code hook _stop() must remove .parallel-failures.jsonl",
        )

    def test_cursor_hook_stop_clears_safety_rails(self):
        self._seed_safety_rails_state()
        self._write_minimal_state(fleet_mode="merging")

        payload = json.dumps({
            "workspace_roots": [str(self.temp_dir)],
            "status": "completed",
            "loop_count": 0,
        })
        result = subprocess.run(
            [sys.executable, str(CURSOR_HOOK)],
            input=payload, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
        # Cursor always exits 0 and prints {} for stop.
        self.assertEqual(json.loads(result.stdout), {})
        self.assertFalse((self.temp_dir / ".harness" / ".invoke-active").exists())
        self.assertFalse(
            self._kill_switch().exists(),
            "Cursor hook _stop() must remove .parallel-disabled",
        )
        self.assertFalse(
            self._failures_log().exists(),
            "Cursor hook _stop() must remove .parallel-failures.jsonl",
        )


class TestConstants(unittest.TestCase):
    def test_threshold_is_two(self):
        self.assertEqual(KILL_SWITCH_THRESHOLD, 2)

    def test_counted_categories(self):
        self.assertEqual(set(COUNTED_CATEGORIES), {"scope_violation", "ambiguity"})


class TestInvokeDocHasNoBatchOfOneSpecialCase(unittest.TestCase):
    """PHASE_009 unit_038: the invoke flow must not carry a 'batch-of-1
    means sequential' special case. The in-tree fast path is gated on
    `len(batch) == 1 AND parallelism.enabled == false`; when parallelism
    is on, a batch-of-1 still takes the worktree path. This pins that
    contract in both the long-form command doc and the workspace-commands
    template so a future edit cannot silently reintroduce the fork.
    """

    LONG_DOC = SKILL_ROOT / "commands" / "invoke.md"
    WORKSPACE_DOC = SKILL_ROOT / "templates" / "workspace-commands" / "invoke-development-harness.md"

    def _load(self, path):
        self.assertTrue(path.exists(), f"doc must exist: {path}")
        return path.read_text(encoding="utf-8")

    def _in_tree_gating_lines(self, body):
        """Return lines that define when the in-tree fast path is chosen.
        Both docs phrase this as a bullet beginning with 'In-tree fast
        path' followed by the gating clause.
        """
        return [
            line for line in body.splitlines()
            if "In-tree fast path" in line and (
                "len(batch) == 1" in line or "batch size" in line.lower()
            )
        ]

    def test_in_tree_gating_always_includes_parallelism_clause(self):
        for doc in (self.LONG_DOC, self.WORKSPACE_DOC):
            body = self._load(doc)
            gating_lines = self._in_tree_gating_lines(body)
            self.assertTrue(
                gating_lines,
                f"{doc.name} must document the in-tree fast-path gating clause",
            )
            for line in gating_lines:
                self.assertIn(
                    "parallelism", line,
                    f"{doc.name} in-tree gating clause must reference "
                    f"parallelism config (not batch size alone): {line!r}",
                )
                self.assertTrue(
                    "false" in line or "disabled" in line.lower(),
                    f"{doc.name} in-tree gating clause must name the "
                    f"parallelism=false half of the condition: {line!r}",
                )

    def test_no_batch_of_one_sequential_antipattern(self):
        """The docs must not describe a 'batch-of-1 -> sequential' fork.
        Sequential is the pre-PHASE_007 shape; the rewrite collapsed it.
        """
        forbidden_substrings = (
            "batch of 1 uses the sequential",
            "batch-of-1 uses the sequential",
            "batch_size == 1 then sequential",
            "if len(batch) == 1: sequential",
            "single-unit sequential path",
        )
        for doc in (self.LONG_DOC, self.WORKSPACE_DOC):
            body = self._load(doc).lower()
            for needle in forbidden_substrings:
                self.assertNotIn(
                    needle, body,
                    f"{doc.name} must not describe a batch-of-1 sequential "
                    f"fork (found: {needle!r})",
                )

    def test_batch_of_one_with_parallelism_on_goes_to_worktree(self):
        """The long-form invoke doc explicitly calls out that a
        batch-of-1 with parallelism on still takes the fan-out path --
        that's exactly what the batch-of-1 equivalence integration test
        exercises. Pin that sentence so it doesn't drift."""
        body = self._load(self.LONG_DOC)
        self.assertIn(
            "len(batch) == 1` when parallelism is on", body,
            "invoke.md must call out that batch-of-1 with parallelism on "
            "still goes through the worktree fan-out path",
        )


if __name__ == "__main__":
    unittest.main()
