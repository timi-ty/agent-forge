#!/usr/bin/env python3
"""Stop hook for development harness invoke loop (Claude Code variant).

PHASE_011 unit_bugfix_002 (ISSUE_002) retired this hook's role as a
block-continue driver. Claude Code's Stop hook protocol has a
one-shot ``stop_hook_active`` guard that persists for the entire
session and a built-in loop-guard floor on top of it -- a Cursor-
style force-continue loop cannot be made reliable. See
``references/claude-code-continuation.md`` for the full explanation.

This hook is now a **precondition checker**. It:

  * Runs the same authority chain as before -- ``.invoke-active``
    flag, ``fleet.mode`` guard, ``loop_budget``, ``blockers``,
    ``open_questions``, selector-vs-checkpoint agreement.
  * Prints one advisory line to stdout describing what it saw:
    either ``proceed: unit_<id> in <phase_id>`` (preconditions met)
    or ``stop: <reason>`` (preconditions failed).
  * Always exits 0. No ``sys.exit(2)``, no ``{"decision": "block"}``.
  * Cleans up session flags (``.invoke-active``, ``.parallel-disabled``,
    ``.parallel-failures.jsonl``) on every path so the next session
    starts clean. The next ``/loop /invoke-development-harness``
    iteration will recreate ``.invoke-active`` on entry.

Multi-turn autonomy on Claude Code uses the native ``/loop`` skill,
not this hook. Idiomatic usage:

    /loop /invoke-development-harness

Each ``/loop`` firing is a fresh session, so ``stop_hook_active``
never accumulates.

Input / Output contract:
- Input: JSON on stdin with ``session_id``, ``cwd``, ``hook_event_name``,
  ``stop_hook_active``.
- Output: one advisory line on stdout (shape: ``<verdict>: <detail>``).
- Exit: always 0.
"""
import json
import os
import subprocess
import sys


def _cleanup(cwd):
    """Clear .invoke-active + session-scoped safety-rail files.

    Called on every exit path; the next /loop iteration will recreate
    .invoke-active when /invoke-development-harness re-enters.
    """
    for name in (".invoke-active", ".parallel-disabled", ".parallel-failures.jsonl"):
        try:
            os.remove(os.path.join(cwd, ".harness", name))
        except OSError:
            pass


def _evaluate(cwd):
    """Run the authority chain. Return an advisory string.

    Shape:
      * ``"proceed: unit_<id> in <phase_id>"`` -- every precondition
        met, next unit is ``<id>``.
      * ``"stop: <reason>"`` -- at least one precondition failed.
    """
    state_path = os.path.join(cwd, ".harness", "state.json")
    if not os.path.exists(state_path):
        return "stop: state.json missing"

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return f"stop: state.json unreadable ({type(exc).__name__})"

    execution = state.get("execution", {})

    fleet_mode = (execution.get("fleet") or {}).get("mode", "idle")
    if fleet_mode != "idle":
        return (
            f"stop: fleet.mode is {fleet_mode!r}; run "
            f"/sync-development-harness to recover"
        )

    loop_count = execution.get("session_count", 0)
    loop_budget = execution.get("loop_budget", 10)
    if loop_count >= loop_budget:
        return f"stop: loop_budget exhausted ({loop_count}/{loop_budget})"

    checkpoint = state.get("checkpoint", {})
    if checkpoint.get("blockers"):
        return "stop: checkpoint.blockers is non-empty"
    if checkpoint.get("open_questions"):
        return "stop: checkpoint.open_questions is non-empty"

    scripts_dir = os.path.join(cwd, ".harness", "scripts")
    selector = os.path.join(scripts_dir, "select_next_unit.py")
    phase_graph = os.path.join(cwd, ".harness", "phase-graph.json")
    if not os.path.exists(selector) or not os.path.exists(phase_graph):
        return "stop: select_next_unit.py or phase-graph.json missing"

    try:
        result = subprocess.run(
            [sys.executable, selector, "--phase-graph", phase_graph],
            capture_output=True, text=True, timeout=10,
        )
        selection = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        return f"stop: select_next_unit.py failed ({type(exc).__name__})"

    if not selection.get("found"):
        return "stop: no next unit (all_complete or blocked)"

    selected_unit = selection.get("unit_id", "")
    selected_phase = selection.get("phase_id", "")
    checkpoint_next = checkpoint.get("next_action", "")
    if checkpoint_next and selected_unit and selected_unit not in checkpoint_next:
        return (
            f"stop: selector says {selected_unit!r} but "
            f"checkpoint.next_action disagrees -- ambiguity"
        )

    return f"proceed: {selected_unit} in {selected_phase}"


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Non-JSON stdin should never happen from Claude Code, but
        # exit cleanly with an advisory rather than raising.
        print("stop: hook stdin was not valid JSON")
        sys.exit(0)

    cwd = input_data.get("cwd", os.getcwd())
    invoke_flag = os.path.join(cwd, ".harness", ".invoke-active")

    # Flag-absent path: silently no-op. Not a harness invoke session.
    if not os.path.exists(invoke_flag):
        sys.exit(0)

    # Evaluate the authority chain, print the advisory, clean up,
    # and exit 0 on every path. Multi-turn autonomy is driven by
    # /loop, not by this hook.
    advisory = _evaluate(cwd)
    print(advisory)
    _cleanup(cwd)
    sys.exit(0)


if __name__ == "__main__":
    main()
