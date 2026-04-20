# Parallel Execution — Deep Reference

This is the operator-facing deep dive on how the harness runs multiple units in a single turn. The high-level summary lives in [architecture.md](./architecture.md) "Parallel Execution Model"; the policy for `touches_paths` enforcement lives in [phase-contract.md](./phase-contract.md) "Scope-Violation Enforcement Policy" and [phase-contract.md](./phase-contract.md) "Decomposing a phase for parallelism". Read those first. This doc is what you consult when a batch fails in an unexpected way.

## 1. Dispatch lifecycle

A parallel turn has exactly one entry point and one exit point. Between them, `state.execution.fleet.mode` transitions through three values and **must** return to `"idle"` before the turn ends.

```
Step 4 (Compute Batch)
    └─ select_next_unit.py --frontier → compute_parallel_batch.py
         └─ batch.json = {batch_id, batch, excluded}

Step 5 (Dispatch) ── dispatch_batch.py ──
    idle → dispatched
    │  per unit:
    │    git worktree add -b harness/<batch_id>/<unit_id>
    │                      .harness/worktrees/<batch_id>/<unit_id> HEAD
    │    write <worktree>/.harness/WORKTREE_UNIT.json
    │    append fleet.units[] entry (status: "running")
    │  atomic on failure → roll back every worktree + branch created
    ▼

Step 6 (Execute) ── one assistant message, N sub-agent calls ──
    dispatched (stays)
    │  Agent(subagent_type: "harness-unit") × N in parallel
    │  wait for all reports, validate structural shape
    ▼

Step 8 (Merge) ── merge_batch.py ──
    dispatched → merging → idle
    │  acquire .harness/.lock (O_EXCL, with stale takeover)
    │  per unit in fleet.units order:
    │    1. scope check: git diff --name-only base..branch
    │         → any file not in touches_paths = hard reject
    │    2. git merge --no-ff harness/<batch_id>/<unit_id>
    │         → clean: status="merged", remove worktree + branch
    │         → conflict: apply conflict_strategy
    │  post-merge validator (optional, via config)
    │    → ok: keep merges
    │    → fail: git reset --hard <pre_merge_ref> + rollback status
    │  release .harness/.lock
    ▼
    idle
```

**Critical invariant:** the stop hook never sees `fleet.mode != "idle"` at turn-end during normal operation. If the hook fires with the fleet in `dispatched` or `merging`, the previous turn crashed mid-batch — recovery is [`/sync-development-harness`](../commands/sync.md) + [`teardown_batch.py`](../scripts/teardown_batch.py), not another invoke turn.

## 2. Overlap-matrix algorithm

`compute_parallel_batch.py` is a greedy packer over an ordered frontier. The packing is deterministic: given the same frontier and config, it always produces the same `(batch, excluded, batch_id)` triple (the `batch_id` component depends on `now`, but the packing decisions don't).

### Inputs

- **Frontier** — list of unit dicts from `select_next_unit.py --frontier`. Each unit must carry at minimum `id`, `parallel_safe`, `touches_paths`, `phase_id`.
- **Parallelism config** — the `config.execution_mode.parallelism` block: `enabled`, `max_concurrent_units`, `conflict_strategy`, `require_touches_paths`, `allow_cross_phase`.

### Algorithm

```
batch = []
excluded = []
batch_phase_id = None        # set once the first unit lands

for unit in frontier:
    # Gate 1: parallel_safe + touches_paths requirement
    if not unit.parallel_safe:
        excluded.append({unit_id, reason: "not_parallel_safe"})
        continue
    if require_touches_paths and not unit.touches_paths:
        excluded.append({unit_id, reason: "not_parallel_safe"})
        continue

    # Gate 2: cross-phase policy (silent defer, NOT excluded)
    if not allow_cross_phase and batch_phase_id is not None:
        if unit.phase_id != batch_phase_id:
            continue   # unit stays on the frontier for a later batch

    # Gate 3: capacity cap
    if len(batch) >= max_concurrent_units:
        excluded.append({unit_id, reason: "capacity_cap"})
        continue

    # Gate 4: pairwise overlap against every unit ALREADY in the batch
    overlap_with = None
    for accepted in batch:
        if _unit_pair_overlaps(unit.touches_paths, accepted.touches_paths):
            overlap_with = accepted.id
            break
    if overlap_with is not None:
        excluded.append({unit_id, reason: f"path_overlap_with:{overlap_with}"})
        continue

    batch.append(unit)
    if batch_phase_id is None:
        batch_phase_id = unit.phase_id

return {batch_id, batch, excluded}
```

### Overlap semantics

Two unit-glob lists overlap if **any** glob from list A matches **any** glob from list B (or vice-versa), using `fnmatch.fnmatchcase`. The check is symmetric. It is also **conservative**: `src/auth/**` and `src/auth/helpers/*.ts` are declared overlapping even if the actual files a unit touches don't collide, because the orchestrator refuses to bet on the sub-agent's restraint. If you see a spurious overlap report, narrow one side's globs — never relax the check.

### Exclusion reasons, verbatim

| Reason string | Meaning |
|---------------|---------|
| `not_parallel_safe` | Unit has `parallel_safe: false`, OR has `parallel_safe: true` with empty `touches_paths` under `require_touches_paths: true`. |
| `capacity_cap` | Batch already at `max_concurrent_units`; unit is eligible for a later turn's frontier. |
| `path_overlap_with:<other_unit_id>` | Unit's `touches_paths` pairwise-overlaps with `<other_unit_id>` already in the batch (via `fnmatch`). |

Cross-phase units are **not** given an exclusion reason — they are silently deferred so the next turn's `select_next_unit.py --frontier` still surfaces them. This is by design: the exclusion list should contain only units the author needs to act on.

## 3. Merge-order rationale

`merge_batch.py` walks `fleet.units` in the order `dispatch_batch.py` appended them — which is the order `compute_parallel_batch.py` accepted them — which is the order the frontier produced them. There is no merge-order optimisation; the order is stable and predictable so failures are reproducible.

**Why no smarter order?** Three reasons:
1. **Determinism beats throughput.** Two runs of the same batch must fail or succeed identically; a heuristic merge order (e.g., "smallest-diff first") would introduce ordering-dependent behaviour.
2. **Scope violations are detected per-unit** before any merge attempt, not via merge conflicts, so there is no "safer order" that avoids them.
3. **Real conflicts are rare** when `touches_paths` is declared correctly. If you are seeing conflicts, the overlap matrix should have caught them at batch-compute time — the fact that it didn't is a bug in the glob declaration, not an ordering problem.

**Merge mode.** Every merge uses `git merge --no-ff -m "harness: merge <unit_id>"`. The explicit merge commit is preserved so `git log --first-parent` on `main` shows one commit per unit, making post-hoc attribution readable.

## 4. Failure-mode catalog

Every failure produces a `fleet.units[].conflict` object with a `category` field. The catalog:

| `category` | Source | `conflict_strategy` effect | Counts toward session kill switch? |
|------------|--------|---------------------------|-------------------------------------|
| `scope_violation` | Pre-merge `git diff --name-only` check in `_scope_violations`. Changed files don't match any `touches_paths` glob. | **None — always hard reject regardless of strategy.** | Yes (`COUNTED_CATEGORIES`). |
| `merge_conflict` | `git merge --no-ff` returns non-zero; `_merge_unit` runs `git merge --abort` and collects `--diff-filter=U` paths. | `abort_batch` (default) fails the batch; `serialize_conflicted` keeps the unit's worktree and continues. | No. |
| `post_merge_validation_failed` | Caller-supplied `run_post_merge_validation` returned `(False, evidence)`. All merged units rolled back via `git reset --hard <pre_merge_ref>`. | **None — always rolls back regardless of strategy.** | No. |
| `infrastructure` | Sub-agent report fails a structural hygiene check (mismatched `unit_id`, invalid `status`, missing commits on `succeeded`, etc.) or the `WORKTREE_UNIT.json` sentinel is unreadable. | Treated as unit failure (skipped from merge) but does NOT trip the kill switch on its own. | No. |
| `ambiguity` | Reserved for cases where the orchestrator cannot decide between two valid next actions (e.g., selector vs checkpoint disagreement). Currently the orchestrator's own stop-and-report path, not produced by `merge_batch.py`. | — | Yes (`COUNTED_CATEGORIES`). |

Two failures in `COUNTED_CATEGORIES` (`scope_violation` or `ambiguity`) in a single invoke session trip the **session kill switch** via [safety_rails.py](../scripts/safety_rails.py): `.harness/.parallel-disabled` is written, and the invoke flow forces the in-tree fast path for the remainder of the session. The switch is cleared when `.invoke-active` is cleared.

## 5. Recovery procedures

### 5.1 Batch crashed mid-dispatch (`fleet.mode == "dispatched"` at turn-end)

Symptom: next turn's stop hook fires and sees a non-idle fleet. Invoke refuses to start.

1. Run [`/sync-development-harness`](../commands/sync.md). It reports orphans via `sync_harness.py`.
2. If the report lists `orphan_worktree`, `stale_fleet_entry`, or `orphan_branch` entries, run `teardown_batch.py --batch-id <batch_id>` to clean them up.
3. Reset `state.execution.fleet` to `{"mode": "idle", "batch_id": null, "units": []}` (either by hand or via `/sync`'s repair flow).
4. Resume with `/invoke-development-harness`.

### 5.2 Batch crashed mid-merge (`fleet.mode == "merging"` at turn-end)

Symptom: as above, but fleet.mode is `"merging"`. Some units may already be merged to `HEAD`, others not.

1. Check `git log --first-parent main` — any `harness: merge <unit_id>` commits since the crash are real merges.
2. For units whose merge commit is on `main`: flip their `fleet.units[].status` to `"merged"` and mark the unit `completed` in `phase-graph.json`.
3. For units not yet merged: decide — re-attempt the merge (keep the worktree), or teardown and re-run the batch from scratch.
4. Release `.harness/.lock` manually if the crashed process left it behind (check file mtime against `lock_stale_after`; `merge_batch.py` will take over a stale lock on its next run).
5. Flip `fleet.mode` to `"idle"` when done.

### 5.3 Session kill switch tripped (`.harness/.parallel-disabled` present)

Symptom: invoke turns silently use the in-tree fast path for single-unit batches even though `parallelism.enabled == true`.

1. Read `.harness/.parallel-failures.jsonl` — each line is a JSON record of a counted failure with `category`, `timestamp`, `unit_id`.
2. Identify the root cause. Two scope_violations in one session almost always means one unit's `touches_paths` is too narrow — fix the declaration in the phase doc.
3. To reset: end the session naturally (the stop hook clears `.invoke-active` + `.parallel-disabled` + `.parallel-failures.jsonl` in one sweep), OR manually delete the files under `.harness/`.

### 5.4 Scope violation reported but the sub-agent insists it was in-bounds

Never trust the sub-agent here. Check the actual diff:

```bash
git -C . diff --name-only $(git merge-base HEAD harness/<batch_id>/<unit_id>)..harness/<batch_id>/<unit_id>
```

Any file in that list that doesn't match the unit's `touches_paths` globs is a genuine scope violation. Options:
- **If the file genuinely belongs to this unit:** update the phase doc's `touches_paths` to include it, commit the phase doc fix, re-run the batch.
- **If the file is spurious (sub-agent wrote somewhere it shouldn't have):** this is a sub-agent contract violation. Log it, revert the unit's branch, investigate the sub-agent's tool allowlist.

### 5.5 Lock contention timeout (`MergeError: timed out waiting for merge lock`)

Symptom: `merge_batch.py` exits with `MergeError` and the lock at `.harness/.lock` is younger than `lock_stale_after`.

1. Another `merge_batch.py` is genuinely running. Wait.
2. If waiting is not an option, check the lock file's PID (first whitespace-separated token in the body) and investigate whether that process is alive.
3. **Never** force-delete the lock without confirming no live merge is in progress — you will get a corrupt merge state.

## 6. Readiness checklist

Before enabling `parallelism.enabled: true` on a project, walk through these questions. Every "no" is a reason to keep parallelism off or scope it further.

- [ ] Does the project have phases with 3+ units that are genuinely independent (no shared files, no read-after-write ordering)?
- [ ] Does every `parallel_safe: true` unit declare a non-empty `touches_paths`?
- [ ] Are `touches_paths` globs narrow enough that the overlap matrix won't reject legitimate pairs?
- [ ] Is there a post-merge validator (linter, tests) configured via the `run_post_merge_validation` callable? Without one, a broken merge lands undetected.
- [ ] Does `/harness-state` render the Fleet & Batch + Orphans + Batch Timings sections correctly on a dry run?
- [ ] Does the project's git config allow `git worktree add` (no conflicting hooks, no filesystem permission issues in `.harness/worktrees/`)?
- [ ] Is the machine on a filesystem that supports `O_EXCL` on file creation? (All major POSIX filesystems do; Windows via Python's `os.open` also works correctly per unit_040's subprocess tests.)
- [ ] Have you dogfooded at least one parallel batch in a throwaway fixture (e.g., by extending [tests/integration/test_invoke_rewrite.py](../scripts/tests/integration/test_invoke_rewrite.py))?

If every box checks, enable parallelism for one phase first. Watch the first few batches. Only then turn it on globally.

## 7. Observability quick reference

For every batch, inspect `.harness/logs/<batch_id>/`:

- `batch.json` — full batch plan, overlap analysis, dispatched fleet (JSON).
- `<unit_id>.md` — sub-agent's per-unit summary (markdown).
- `merge.log` — grep-friendly merge-outcomes summary (text).
- `validation.log` — post-merge validator output (text).

`/harness-state` renders these alongside `fleet` and `sync_harness.py` orphan detection. The [Batch Timings](../commands/state.md) section pins the one-line format:

```
Batch <batch_id>: dispatched HH:MM:SS, merged HH:MM:SS, total Ns
```

These logs are harness-owned and gitignored (see `.harness/.gitignore`). They persist across sessions until `/clear` removes them.
