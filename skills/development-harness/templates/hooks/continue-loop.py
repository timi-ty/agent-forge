#!/usr/bin/env python3
"""Stop hook for development harness invoke loop (Cursor variant).

Authority chain:
0. Check .invoke-active flag (only harness invoke sessions create this).
1. Check status (only continue on "completed").
2. Read state.json. **Fleet-mode guard:** if
   `state.execution.fleet.mode != "idle"`, a previous turn crashed
   mid-batch -- stop and require `/sync-development-harness` to
   recover. Missing `fleet` block (v1-style state) is treated as idle.
3. Check loop budget.
4. Check blockers and open questions.
5. Run select_next_unit.py for authoritative next unit.
6. Compare against checkpoint.next_action.
7. If they disagree, STOP (disagreement = ambiguity).
8. Otherwise, return followup_message to continue.
"""
import json
import os
import subprocess
import sys


def main():
    input_data = json.load(sys.stdin)
    workspace_roots = input_data.get("workspace_roots", [])
    root = workspace_roots[0] if workspace_roots else os.getcwd()

    invoke_flag = os.path.join(root, ".harness", ".invoke-active")
    if not os.path.exists(invoke_flag):
        _stop()
        return

    status = input_data.get("status", "")
    loop_count = input_data.get("loop_count", 0)

    if status != "completed":
        _stop(invoke_flag)
        return

    state_path = os.path.join(root, ".harness", "state.json")

    if not os.path.exists(state_path):
        _stop(invoke_flag)
        return

    with open(state_path, "r") as f:
        state = json.load(f)

    # Fleet-mode guard: if a previous turn crashed mid-batch, fleet.mode
    # is still 'dispatched' or 'merging'. Stop immediately -- recovery
    # goes through /sync-development-harness. Missing fleet block (v1
    # state shape) is treated as idle so old state files keep working.
    execution = state.get("execution", {})
    fleet_mode = (execution.get("fleet") or {}).get("mode", "idle")
    if fleet_mode != "idle":
        _stop(invoke_flag)
        return

    loop_budget = execution.get("loop_budget", 10)
    if loop_count >= loop_budget:
        _stop(invoke_flag)
        return

    checkpoint = state.get("checkpoint", {})
    if checkpoint.get("blockers"):
        _stop(invoke_flag)
        return
    if checkpoint.get("open_questions"):
        _stop(invoke_flag)
        return

    scripts_dir = os.path.join(root, ".harness", "scripts")
    selector = os.path.join(scripts_dir, "select_next_unit.py")
    phase_graph = os.path.join(root, ".harness", "phase-graph.json")

    if not os.path.exists(selector) or not os.path.exists(phase_graph):
        _stop(invoke_flag)
        return

    try:
        result = subprocess.run(
            [sys.executable, selector, "--phase-graph", phase_graph],
            capture_output=True, text=True, timeout=10
        )
        selection = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        _stop(invoke_flag)
        return

    if not selection.get("found"):
        _stop(invoke_flag)
        return

    selected_unit = selection.get("unit_id", "")
    selected_phase = selection.get("phase_id", "")
    checkpoint_next = checkpoint.get("next_action", "")

    if checkpoint_next and selected_unit and selected_unit not in checkpoint_next:
        _stop(invoke_flag)
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


def _stop(invoke_flag=None):
    # Clear .invoke-active AND the session-scoped safety-rail files
    # (kill switch + failure log). invoke_flag carries the absolute
    # path to .invoke-active; the companion files live alongside it.
    if invoke_flag:
        harness_dir = os.path.dirname(invoke_flag)
        for name in (".invoke-active", ".parallel-disabled", ".parallel-failures.jsonl"):
            try:
                os.remove(os.path.join(harness_dir, name))
            except OSError:
                pass
    print(json.dumps({}))


if __name__ == "__main__":
    main()
