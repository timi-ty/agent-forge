#!/usr/bin/env python3
"""Stop hook for development harness invoke loop (Claude Code variant).

Claude Code hook protocol:
- Input: JSON on stdin with session_id, cwd, hook_event_name, stop_hook_active
- Exit 0: allow Claude to stop
- Exit 2: block stopping; stdout JSON with decision/reason is fed back

Authority chain:
0. Respect stop_hook_active (Claude Code's built-in loop guard)
1. Check .invoke-active flag (only harness invoke sessions create this)
2. Read state.json for loop budget, blockers, open questions
3. Run select_next_unit.py for authoritative next unit
4. Compare against checkpoint.next_action
5. If they disagree, STOP (disagreement = ambiguity)
6. Otherwise, exit 2 to block stopping and continue
"""
import json
import os
import subprocess
import sys


def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", os.getcwd())

    # Respect Claude Code's built-in loop guard
    if input_data.get("stop_hook_active", False):
        _stop(cwd)
        return

    # Session gate: only harness invoke sessions set this flag
    invoke_flag = os.path.join(cwd, ".harness", ".invoke-active")
    if not os.path.exists(invoke_flag):
        sys.exit(0)  # Not a harness session, allow stop
        return

    state_path = os.path.join(cwd, ".harness", "state.json")
    if not os.path.exists(state_path):
        _stop(cwd)
        return

    with open(state_path, "r") as f:
        state = json.load(f)

    # Read loop count from state (Claude Code doesn't provide loop_count)
    execution = state.get("execution", {})
    loop_count = execution.get("session_count", 0)
    loop_budget = execution.get("loop_budget", 10)

    if loop_count >= loop_budget:
        _stop(cwd)
        return

    checkpoint = state.get("checkpoint", {})
    if checkpoint.get("blockers"):
        _stop(cwd)
        return
    if checkpoint.get("open_questions"):
        _stop(cwd)
        return

    scripts_dir = os.path.join(cwd, ".harness", "scripts")
    selector = os.path.join(scripts_dir, "select_next_unit.py")
    phase_graph = os.path.join(cwd, ".harness", "phase-graph.json")

    if not os.path.exists(selector) or not os.path.exists(phase_graph):
        _stop(cwd)
        return

    try:
        result = subprocess.run(
            [sys.executable, selector, "--phase-graph", phase_graph],
            capture_output=True, text=True, timeout=10
        )
        selection = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        _stop(cwd)
        return

    if not selection.get("found"):
        _stop(cwd)
        return

    selected_unit = selection.get("unit_id", "")
    selected_phase = selection.get("phase_id", "")
    checkpoint_next = checkpoint.get("next_action", "")

    if checkpoint_next and selected_unit and selected_unit not in checkpoint_next:
        _stop(cwd)
        return

    # Block stopping -- feed continuation instruction to Claude Code
    desc = selection.get("unit_description", selected_unit)
    message = (
        f"[Harness iteration {loop_count + 1}/{loop_budget}] "
        f"Continue with unit {selected_unit} in {selected_phase}: {desc}. "
        f"Read .harness/checkpoint.md for context, then follow "
        f"/invoke-development-harness workflow."
    )
    print(json.dumps({"decision": "block", "reason": message}))
    sys.exit(2)


def _stop(cwd):
    invoke_flag = os.path.join(cwd, ".harness", ".invoke-active")
    try:
        os.remove(invoke_flag)
    except OSError:
        pass
    sys.exit(0)  # Allow Claude to stop


if __name__ == "__main__":
    main()
