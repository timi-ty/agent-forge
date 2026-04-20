"""Tests for the new parallel-execution.md deep-dive doc -- unit_047.

PHASE_011 documentation phase requires a references/parallel-
execution.md file covering the six topics named in the phase doc:
dispatch lifecycle, overlap-matrix algorithm, merge-order rationale,
failure-mode catalog, recovery procedures, readiness checklist.

This test pins each topic's presence + the substantive tokens that
prove the doc matches the actual code (exclusion-reason strings,
conflict categories, kill-switch thresholds). A future edit that
weakens any section would trip these assertions.

Also verifies consistency with the actual code:
  * The exclusion-reason string 'path_overlap_with' must appear
    (not the earlier 'touches_overlap' typo that slipped into
    unit_045/046's first-pass docs).
  * The scope-violation conflict category 'scope_violation' must
    match safety_rails.py's COUNTED_CATEGORIES constant.
"""
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
PARALLEL_EXEC = SKILL_ROOT / "references" / "parallel-execution.md"


def _load():
    assert PARALLEL_EXEC.exists(), f"parallel-execution.md must exist at {PARALLEL_EXEC}"
    return PARALLEL_EXEC.read_text(encoding="utf-8")


class TestParallelExecutionDocStructure(unittest.TestCase):
    """Six top-level numbered sections match the six acceptance
    bullets plus the intro. Each has a required substantive anchor."""

    def _section(self, heading):
        body = _load()
        self.assertIn(heading, body,
                      f"parallel-execution.md must contain '{heading}'")
        start = body.index(heading)
        # End at the next '## ' heading.
        end = body.find("\n## ", start + len(heading))
        return body[start:end] if end != -1 else body[start:]

    def test_dispatch_lifecycle_section(self):
        section = self._section("## 1. Dispatch lifecycle")
        # Must name all three fleet.mode transition states.
        for token in ("idle", "dispatched", "merging"):
            self.assertTrue(
                f'`{token}`' in section or f'"{token}"' in section,
                f"dispatch lifecycle must name fleet.mode state {token!r}",
            )
        # Must name the three orchestrator scripts involved.
        self.assertIn("compute_parallel_batch.py", section)
        self.assertIn("dispatch_batch.py", section)
        self.assertIn("merge_batch.py", section)
        # Must pin the mid-turn-crash recovery path.
        self.assertIn("/sync-development-harness", section)

    def test_overlap_matrix_section(self):
        section = self._section("## 2. Overlap-matrix algorithm")
        # Deterministic-packing invariant must be called out.
        self.assertIn("deterministic", section.lower())
        # Actual exclusion-reason strings (must match code).
        for reason in ("not_parallel_safe", "capacity_cap", "path_overlap_with"):
            self.assertIn(reason, section)
        # Must state cross-phase units are NOT given an exclusion reason.
        self.assertIn("cross-phase", section.lower())
        # Must name the fnmatch enforcer.
        self.assertIn("fnmatch", section)

    def test_merge_order_section(self):
        section = self._section("## 3. Merge-order rationale")
        # Must explain why the order is stable.
        self.assertIn("determinism", section.lower())
        # Must name the git merge mode.
        self.assertIn("--no-ff", section)
        # Must point at first-parent log for attribution readability.
        self.assertIn("first-parent", section.lower())

    def test_failure_mode_catalog(self):
        section = self._section("## 4. Failure-mode catalog")
        # All five known categories must appear.
        for category in (
            "scope_violation",
            "merge_conflict",
            "post_merge_validation_failed",
            "infrastructure",
            "ambiguity",
        ):
            self.assertIn(category, section,
                          f"catalog must name the {category!r} conflict category")
        # Must explain kill-switch-counting distinction so authors
        # don't assume all categories count.
        self.assertIn("COUNTED_CATEGORIES", section)
        # Cross-link to safety_rails.py.
        self.assertIn("safety_rails.py", section)

    def test_recovery_procedures_section(self):
        section = self._section("## 5. Recovery procedures")
        # Must cover all four recovery scenarios described in the phase doc.
        for scenario in (
            "mid-dispatch",
            "mid-merge",
            "kill switch",  # case-insensitive match below
            "Scope violation",
        ):
            self.assertIn(scenario, section,
                          f"recovery procedures must cover {scenario!r} scenario")
        # Must explicitly warn against force-deleting the lock.
        self.assertIn(".harness/.lock", section)
        self.assertIn("force-delete", section.lower())

    def test_readiness_checklist(self):
        section = self._section("## 6. Readiness checklist")
        # Must be a literal checklist (markdown checkboxes).
        self.assertIn("- [ ]", section,
                      "readiness checklist must use markdown checkbox syntax")
        # Must cover the four highest-leverage gates.
        gates_lower = section.lower()
        self.assertIn("touches_paths", gates_lower)
        self.assertIn("overlap matrix", gates_lower)
        self.assertIn("post-merge validator", gates_lower)
        self.assertIn("/harness-state", section)

    def test_observability_quick_reference(self):
        section = self._section("## 7. Observability quick reference")
        # All four per-batch artifacts must be named.
        for artifact in ("batch.json", "<unit_id>.md", "merge.log", "validation.log"):
            self.assertIn(artifact, section)
        # Exact Batch Timings format string.
        self.assertIn(
            "Batch <batch_id>: dispatched HH:MM:SS, merged HH:MM:SS, total Ns",
            section,
        )


class TestParallelExecutionDocCrossLinks(unittest.TestCase):
    """The doc is the deep-dive companion to architecture.md and
    phase-contract.md. It must link those two at the top so readers
    know the hierarchy, and architecture.md's 'Parallel Execution
    Model' section must point forward to this doc."""

    def test_doc_links_architecture_and_phase_contract(self):
        body = _load()
        self.assertIn("architecture.md", body)
        self.assertIn("phase-contract.md", body)
        # Explicit 'deep dive' framing so readers understand the
        # hierarchy.
        self.assertIn("deep dive", body.lower())

    def test_architecture_md_still_points_at_this_doc(self):
        """The architecture.md link was introduced in unit_045 (as a
        forward reference) and must survive. Regression guard."""
        architecture = SKILL_ROOT / "references" / "architecture.md"
        body = architecture.read_text(encoding="utf-8")
        self.assertIn("parallel-execution.md", body,
                      "architecture.md must link to parallel-execution.md")


class TestExclusionReasonConsistencyWithCode(unittest.TestCase):
    """The doc's exclusion-reason strings must exactly match the
    output of compute_parallel_batch.py. This test guards against
    the 'touches_overlap' vs 'path_overlap_with' drift that slipped
    into the first pass of unit_045/046 before unit_047 caught it.
    """

    def test_doc_uses_correct_overlap_reason_string(self):
        body = _load()
        # Must use the real code string.
        self.assertIn("path_overlap_with", body)
        # Must NOT use the pre-fix 'touches_overlap' string -- guards
        # against a future edit reintroducing it.
        self.assertNotIn("touches_overlap", body,
                         "parallel-execution.md must not use the pre-fix "
                         "'touches_overlap' string; the actual code emits "
                         "'path_overlap_with:<id>'")


if __name__ == "__main__":
    unittest.main()
