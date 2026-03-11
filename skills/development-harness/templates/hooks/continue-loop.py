#!/usr/bin/env python3
"""Stop hook for development harness invoke loop.

Authority chain:
1. Check status (only continue on "completed")
2. Check loop budget
3. Check blockers and open questions
4. Run select_next_unit.py for authoritative next unit
5. Compare against checkpoint.next_action
6. If they disagree, STOP (disagreement = ambiguity)
7. Otherwise, return followup_message to continue
"""
import json
import os
import subprocess
import sys


def main():
    input_data = json.load(sys.stdin)
    status = input_data.get("status", "")
    loop_count = input_data.get("loop_count", 0)

    if status != "completed":
        _stop()
        return

    workspace_roots = input_data.get("workspace_roots", [])
    root = workspace_roots[0] if workspace_roots else os.getcwd()
    state_path = os.path.join(root, ".harness", "state.json")

    if not os.path.exists(state_path):
        _stop()
        return

    with open(state_path, "r") as f:
        state = json.load(f)

    loop_budget = state.get("execution", {}).get("loop_budget", 10)
    if loop_count >= loop_budget:
        _stop()
        return

    checkpoint = state.get("checkpoint", {})
    if checkpoint.get("blockers"):
        _stop()
        return
    if checkpoint.get("open_questions"):
        _stop()
        return

    # Run select_next_unit.py as the authoritative source
    scripts_dir = os.path.join(root, ".harness", "scripts")
    selector = os.path.join(scripts_dir, "select_next_unit.py")
    phase_graph = os.path.join(root, ".harness", "phase-graph.json")

    if not os.path.exists(selector) or not os.path.exists(phase_graph):
        _stop()
        return

    try:
        result = subprocess.run(
            [sys.executable, selector, "--phase-graph", phase_graph],
            capture_output=True, text=True, timeout=10
        )
        selection = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        _stop()
        return

    if not selection.get("found"):
        _stop()
        return

    selected_unit = selection.get("unit_id", "")
    selected_phase = selection.get("phase_id", "")
    checkpoint_next = checkpoint.get("next_action", "")

    # If checkpoint disagrees with selector, stop (ambiguity)
    if checkpoint_next and selected_unit and selected_unit not in checkpoint_next:
        _stop()
        return

    desc = selection.get("unit_description", selected_unit)
    print(json.dumps({
        "followup_message": (
            f"[Harness iteration {loop_count + 1}/{loop_budget}] "
            f"Continue with unit {selected_unit} in {selected_phase}: {desc}. "
            f"Read .harness/checkpoint.md for context, then follow "
            f"/invoke-development-harness workflow."
        )
    }))


def _stop():
    print(json.dumps({}))


if __name__ == "__main__":
    main()
