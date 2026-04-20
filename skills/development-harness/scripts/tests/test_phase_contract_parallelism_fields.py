"""Tests for the parallelism-field + decomposition additions to
phase-contract.md -- unit_046.

PHASE_011 documentation phase requires phase-contract.md to document
depends_on, parallel_safe, and touches_paths as required unit fields
(with parallel_safe required-gating touches_paths), AND to add a
'Decomposing a phase for parallelism' subsection with practical
guidance.

This module pins both pieces of content at the doc level so a future
edit can't silently drop coverage. Pairs with test_safety_rails.py's
TestScopeViolationAlwaysOnPolicy (unit_039) which pins the pre-
existing Scope-Violation Enforcement Policy in the same doc.
"""
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
PHASE_CONTRACT = SKILL_ROOT / "references" / "phase-contract.md"


def _load():
    assert PHASE_CONTRACT.exists(), f"phase-contract.md must exist at {PHASE_CONTRACT}"
    return PHASE_CONTRACT.read_text(encoding="utf-8")


class TestUnitsOfWorkTableCarriesParallelismFields(unittest.TestCase):
    """The Units of Work table must carry a row for each of the three
    parallelism-governing fields: depends_on, parallel_safe, and
    touches_paths. Each row must state when the field is required so
    phase authors can't misunderstand touches_paths's conditional
    requirement."""

    def _units_of_work_section(self):
        body = _load()
        start_marker = "### Units of Work"
        self.assertIn(start_marker, body)
        start = body.index(start_marker)
        end = body.find("\n### ", start + len(start_marker))
        return body[start:end] if end != -1 else body[start:]

    def test_table_has_required_column(self):
        """Without a 'Required' column the when-required semantics for
        touches_paths are implicit. Adding it is the edit unit_046
        makes."""
        section = self._units_of_work_section()
        self.assertIn("| **id** |", section,
                      "table must carry the existing id row")
        self.assertIn("| Required |", section,
                      "Units of Work table must gain a 'Required' column")

    def test_table_documents_depends_on(self):
        section = self._units_of_work_section()
        self.assertIn("**depends_on**", section,
                      "table must carry a depends_on row")
        # Must name the enforcer script.
        self.assertIn("compute_frontier", section,
                      "depends_on row must name compute_frontier as the gate")

    def test_table_documents_parallel_safe(self):
        section = self._units_of_work_section()
        self.assertIn("**parallel_safe**", section)
        self.assertIn("compute_parallel_batch.py", section,
                      "parallel_safe row must name compute_parallel_batch.py")
        self.assertIn("in-tree fast path", section,
                      "parallel_safe row must describe the false path")

    def test_table_documents_touches_paths_with_conditional_requirement(self):
        """touches_paths is the most error-prone row -- it is required
        ONLY when parallel_safe is true (under default config). Pin
        that the conditional is stated explicitly."""
        section = self._units_of_work_section()
        self.assertIn("**touches_paths**", section)
        self.assertTrue(
            "required when `parallel_safe: true`" in section or
            "required when ``parallel_safe: true``" in section or
            "required when parallel_safe: true" in section,
            "touches_paths row must name the conditional "
            "'required when parallel_safe: true'",
        )
        # Cross-link to the Scope-Violation policy so readers follow
        # the why.
        self.assertIn("Scope-Violation Enforcement Policy", section,
                      "touches_paths row must cross-link to the enforcement policy")


class TestDecompositionSubsection(unittest.TestCase):
    """The 'Decomposing a phase for parallelism' subsection is the
    how-to companion to the Units of Work table. Pin its presence
    and the five-step structure so a future edit can't gut it."""

    def _section(self):
        body = _load()
        heading = "## Decomposing a phase for parallelism"
        self.assertIn(heading, body,
                      f"phase-contract.md must carry a '{heading}' top-level heading")
        start = body.index(heading)
        # This section may be the last one in the doc; both branches handled.
        end = body.find("\n## ", start + len(heading))
        return body[start:end] if end != -1 else body[start:]

    def test_section_present(self):
        self._section()  # triggers the existence assertion

    def test_section_has_five_steps(self):
        """The checklist shape (Step 1..Step 5) is deliberate -- it
        walks phase authors through the decomposition in order. Drop
        a step and the guidance becomes a vibe check instead of a
        recipe."""
        section = self._section()
        for n in (1, 2, 3, 4, 5):
            self.assertIn(
                f"### Step {n}", section,
                f"Decomposition subsection must carry a 'Step {n}' sub-heading",
            )

    def test_section_names_dependency_graph(self):
        """Step 1: dependency graph authoring. Must distinguish real
        depends_on from spurious logical-ordering preferences."""
        section = self._section()
        self.assertIn("dependency graph", section.lower())
        # Must discuss both real and not-real dependency kinds so
        # readers don't over-declare.
        self.assertIn("NOT real", section)

    def test_section_covers_blast_radius_and_overlap_heuristics(self):
        """Step 2-3: touches_paths authoring + overlap check."""
        section = self._section()
        self.assertIn("blast radius", section.lower())
        self.assertIn("one directory per unit", section.lower(),
                      "decomposition must name the one-directory-per-unit heuristic")
        self.assertIn("overlap matrix", section.lower())
        self.assertIn("path_overlap_with", section,
                      "must name the excluded-reason string agents will see "
                      "(matches compute_parallel_batch.py output)")

    def test_section_covers_parallel_safe_four_criteria(self):
        """Step 4: parallel_safe is a declaration of independence, not
        a performance hint. Pin the four criteria so authors don't
        set it for the wrong reason."""
        section = self._section()
        self.assertIn("declaration of independence", section.lower())
        # Hint vs declaration contrast must be explicit.
        self.assertIn("performance hint", section.lower())

    def test_section_covers_dry_run_and_anti_patterns(self):
        """Step 5 + anti-patterns: practical guardrails."""
        section = self._section()
        self.assertIn("select_next_unit.py --frontier", section)
        self.assertIn("compute_parallel_batch.py", section)
        self.assertIn("Anti-patterns", section,
                      "decomposition must carry an Anti-patterns sub-heading")


class TestDecompositionSectionPlacedAfterScopePolicy(unittest.TestCase):
    """The Decomposing section must come AFTER the Scope-Violation
    Enforcement Policy so readers encounter the 'why touches_paths is
    a trust boundary' context before the 'how to partition a phase'
    guidance. A future edit that moves the section above the policy
    would damage the reading flow -- this test catches that."""

    def test_scope_policy_precedes_decomposition(self):
        body = _load()
        idx_scope = body.find("## Scope-Violation Enforcement Policy")
        idx_decomp = body.find("## Decomposing a phase for parallelism")
        self.assertNotEqual(idx_scope, -1)
        self.assertNotEqual(idx_decomp, -1)
        self.assertLess(
            idx_scope, idx_decomp,
            "Scope-Violation Enforcement Policy must appear BEFORE the "
            "Decomposing subsection so the trust-boundary rationale is "
            "read first",
        )


if __name__ == "__main__":
    unittest.main()
