"""Tests for the 'Parallel Execution Model' section in architecture.md
-- unit_045.

PHASE_011 documentation phase requires architecture.md to carry a
complete Parallel Execution Model section covering the six topics
named in PHASE_011_documentation.md's phase doc: worktree-per-unit,
orchestrator/sub-agent boundary, frontier+overlap check, dispatch-
wait-merge lifecycle, conflict strategies, when to enable/not. This
test module pins each topic's presence so a future edit cannot
silently drop coverage.

No runtime script interprets this doc -- it is reference material
for human readers and for the agent bootstrapping new projects via
create.md. The regression guard is a doc-shape contract.
"""
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURE = SKILL_ROOT / "references" / "architecture.md"


class TestArchitectureParallelExecutionSection(unittest.TestCase):
    def _load(self):
        self.assertTrue(
            ARCHITECTURE.exists(),
            f"architecture.md must exist at {ARCHITECTURE}",
        )
        return ARCHITECTURE.read_text(encoding="utf-8")

    def _section(self, body, heading="## Parallel Execution Model"):
        """Slice out the 'Parallel Execution Model' section so subtopic
        assertions don't accidentally match headings from elsewhere in
        the doc."""
        self.assertIn(
            heading, body,
            f"architecture.md must contain a '{heading}' second-level heading",
        )
        start = body.index(heading)
        # Next '## ' heading ends the section.
        end = body.find("\n## ", start + len(heading))
        return body[start:end] if end != -1 else body[start:]

    def test_section_heading_present(self):
        body = self._load()
        self.assertIn("## Parallel Execution Model", body,
                      "architecture.md must carry the new section heading")

    def test_section_covers_when_to_enable(self):
        """Acceptance bullet: 'when to enable/not'."""
        section = self._section(self._load())
        self.assertIn("### When to enable parallelism", section)
        # Must name the config path explicitly so readers know the knob.
        self.assertIn("config.execution_mode.parallelism", section)
        # Must name the gating field a candidate unit needs.
        self.assertIn("parallel_safe", section)
        self.assertIn("depends_on", section)
        self.assertIn("touches_paths", section)

    def test_section_covers_worktree_per_unit_layout(self):
        """Acceptance bullet: 'worktree-per-unit'."""
        section = self._section(self._load())
        self.assertIn("### Worktree-per-unit layout", section)
        # Must name the on-disk path template and the branch template.
        self.assertIn(".harness/worktrees/<batch_id>/<unit_id>/", section)
        self.assertIn("harness/<batch_id>/<unit_id>", section)
        # Must name the sentinel file so the merge-time scope check
        # has a source-of-truth anchor.
        self.assertIn("WORKTREE_UNIT.json", section)

    def test_section_covers_orchestrator_subagent_boundary(self):
        """Acceptance bullet: 'orchestrator/sub-agent boundary'."""
        section = self._section(self._load())
        self.assertIn("### Orchestrator / sub-agent boundary", section)
        # Must name the sub-agent type string used in dispatch.
        self.assertIn('subagent_type: "harness-unit"', section)
        # Must call out the tight-allowlist guarantees.
        section_lower = section.lower()
        self.assertIn("no `git push`", section_lower)
        # Must state that the sub-agent's self-report is not trusted.
        self.assertIn("never", section_lower)
        self.assertIn("self-report", section_lower)

    def test_section_covers_frontier_and_overlap(self):
        """Acceptance bullet: 'frontier+overlap check'."""
        section = self._section(self._load())
        self.assertIn("### Frontier + overlap check", section)
        self.assertIn("select_next_unit.py --frontier", section)
        self.assertIn("compute_parallel_batch.py", section)
        # Overlap matrix must be called out explicitly.
        self.assertIn("Overlap matrix", section)
        self.assertIn("fnmatch", section)
        self.assertIn("path_overlap_with", section,
                      "overlap exclusion-reason must match the actual "
                      "compute_parallel_batch.py output string")

    def test_section_covers_dispatch_wait_merge_lifecycle(self):
        """Acceptance bullet: 'dispatch-wait-merge lifecycle'."""
        section = self._section(self._load())
        self.assertIn("### Dispatch → wait → merge lifecycle", section)
        # fleet.mode transitions must be pinned so readers know what
        # /harness-state will display and what /sync recovers from.
        # Accept either markdown-code (`idle`) or JSON-style ("idle")
        # framing so the test doesn't fail on stylistic quoting choices.
        for state in ("idle", "dispatched", "merging"):
            self.assertTrue(
                f'`{state}`' in section or f'"{state}"' in section,
                f"lifecycle must name fleet.mode state {state!r} "
                f"(in `{state}` or \"{state}\" form)",
            )
        # Scope-check timing must be pinned: BEFORE the merge attempt.
        self.assertIn("BEFORE the merge attempt", section)

    def test_section_covers_conflict_strategies(self):
        """Acceptance bullet: 'conflict strategies'."""
        section = self._section(self._load())
        self.assertIn("### Conflict strategies", section)
        self.assertIn("abort_batch", section)
        self.assertIn("serialize_conflicted", section)
        self.assertIn("(default)", section,
                      "must name abort_batch as the default")
        # Must cross-reference the scope-violation always-on rule so a
        # reader comparing abort_batch vs serialize_conflicted does not
        # assume a looser strategy relaxes scope enforcement.
        self.assertIn("phase-contract.md", section)

    def test_section_covers_merge_lock(self):
        """Not an explicit acceptance bullet, but the lifecycle is
        incomplete without naming the concurrency control. The
        dispatch-wait-merge flow only works because of .harness/.lock."""
        section = self._section(self._load())
        self.assertIn(".harness/.lock", section)
        self.assertIn("O_EXCL", section)

    def test_section_covers_safety_rails_and_observability(self):
        """These are the PHASE_009 + PHASE_010 hand-offs -- the
        architecture doc must link to the session kill switch and
        the per-batch log artifacts so readers do not need to dig
        through phase docs to find them."""
        section = self._section(self._load())
        # Safety rails (PHASE_009).
        self.assertIn(".parallel-disabled", section)
        self.assertIn("safety_rails.py", section)
        # Observability (PHASE_010).
        self.assertIn(".harness/logs/<batch_id>/", section)
        for artifact in ("batch.json", "merge.log", "validation.log"):
            self.assertIn(artifact, section)

    def test_section_places_before_git_integration(self):
        """Pin the insertion point. The new section must come AFTER
        'Batch Semantics' (the narrowest-scope existing parallel topic)
        and BEFORE 'Git Integration' (the downstream topic). A future
        edit that accidentally moves or duplicates the section would
        violate one of these orderings.
        """
        body = self._load()
        idx_batch_semantics = body.find("## Batch Semantics")
        idx_parallel = body.find("## Parallel Execution Model")
        idx_git = body.find("## Git Integration")
        self.assertNotEqual(idx_batch_semantics, -1)
        self.assertNotEqual(idx_parallel, -1)
        self.assertNotEqual(idx_git, -1)
        self.assertLess(idx_batch_semantics, idx_parallel,
                        "Parallel Execution Model must come after Batch Semantics")
        self.assertLess(idx_parallel, idx_git,
                        "Parallel Execution Model must come before Git Integration")


if __name__ == "__main__":
    unittest.main()
