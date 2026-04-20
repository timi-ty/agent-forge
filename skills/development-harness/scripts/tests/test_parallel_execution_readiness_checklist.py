"""Tests for the parallelism readiness checklist extensions -- unit_051.

PHASE_012 release-readiness requires three new readiness checks to
be present in skills/development-harness/references/parallel-execution.md's
'Readiness checklist' section (originally scaffolded at 8 items in
unit_047):

  1. touches_paths declared on every parallelism-eligible unit
  2. No pending unit modifies a shared aggregator file
  3. CI handles multi-commit pushes

Each check is a gating concern from real dogfood experience --
aggregators silently collide, CI systems with per-commit hooks
choke on multi-commit pushes, and a missing touches_paths
declaration turns a unit into a scope-violation timebomb at merge
time. This test pins each check's presence + rationale wording so
a future edit cannot silently drop one.

Pairs with test_parallel_execution_reference.py (unit_047) which
pins the broader structure of the doc; this module focuses on the
three PHASE_012 checklist additions specifically.
"""
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
PARALLEL_EXEC = SKILL_ROOT / "references" / "parallel-execution.md"


def _load():
    assert PARALLEL_EXEC.exists(), f"parallel-execution.md must exist at {PARALLEL_EXEC}"
    return PARALLEL_EXEC.read_text(encoding="utf-8")


def _readiness_section():
    body = _load()
    heading = "## 6. Readiness checklist"
    assert heading in body, f"parallel-execution.md must carry '{heading}'"
    start = body.index(heading)
    end = body.find("\n## ", start + len(heading))
    return body[start:end] if end != -1 else body[start:]


class TestReadinessChecklistHasUnitDeclarationSubsection(unittest.TestCase):
    """The pre-unit_051 list was flat. unit_051 splits it into
    'Unit-declaration readiness' + 'Runtime & infrastructure readiness'
    so the 3 new unit-declaration-oriented checks sit next to the
    pre-existing declaration check, not scattered across the list."""

    def test_unit_declaration_subheading(self):
        section = _readiness_section()
        self.assertIn("### Unit-declaration readiness", section,
                      "Readiness checklist must have a 'Unit-declaration readiness' sub-heading")

    def test_runtime_subheading(self):
        section = _readiness_section()
        self.assertIn("### Runtime & infrastructure readiness", section,
                      "Readiness checklist must have a 'Runtime & infrastructure readiness' sub-heading")


class TestReadinessChecklistTouchesPathsCheck(unittest.TestCase):
    """Acceptance bullet 1: touches_paths on every parallelism-
    eligible unit. Must be a strengthened check -- the pre-unit_051
    question 'Does every parallel_safe: true unit declare touches_paths'
    is fine but lacks the 'walk every phase doc's table' action
    guidance that makes it actually useful."""

    def test_check_is_bolded_for_emphasis(self):
        """Bolded checks in the readiness list mark the unit_051
        additions so readers can distinguish them from the
        pre-unit_047 baseline. The bolding is load-bearing -- test
        pins it."""
        section = _readiness_section()
        self.assertIn(
            "**Does every parallelism-eligible unit declare `touches_paths`?**",
            section,
            "touches_paths check must be bolded and phrased exactly",
        )

    def test_check_names_rejection_reason(self):
        """Must tell the reader what specifically goes wrong
        (not_parallel_safe exclusion under require_touches_paths:
        true default). Generic 'declare touches_paths' without the
        downstream consequence is a weaker check."""
        section = _readiness_section()
        self.assertIn("not_parallel_safe", section)
        self.assertIn("require_touches_paths", section)

    def test_check_cross_links_scope_violation_policy(self):
        section = _readiness_section()
        self.assertIn("phase-contract.md", section)
        self.assertIn("Scope-Violation Enforcement Policy", section)


class TestReadinessChecklistSharedAggregatorCheck(unittest.TestCase):
    """Acceptance bullet 2: no shared-aggregator units. This is the
    most subtle of the three -- aggregators LOOK parallel-safe
    (narrow touches_paths, one unit) but cause silent merge conflicts
    with siblings. The check must explicitly name the pattern."""

    def test_check_bolded_and_phrased_exactly(self):
        section = _readiness_section()
        self.assertIn(
            "**Are there no shared-aggregator units?**",
            section,
            "shared-aggregator check must be bolded with exact question wording",
        )

    def test_check_defines_aggregator(self):
        """Without a definition, readers won't recognize the pattern.
        The doc must name concrete examples so authors can match
        their own unit types."""
        section = _readiness_section()
        self.assertIn("aggregator is a unit", section.lower(),
                      "check must define 'aggregator'")
        # At least 3 concrete examples so the pattern is recognizable
        # across stacks.
        for example in ("router", "index.ts", "__init__.py"):
            self.assertIn(example, section,
                          f"aggregator check must name {example!r} as an example")

    def test_check_proposes_concrete_remediation(self):
        """Actionable checks beat descriptive ones. The aggregator
        check must propose two specific fixes: absorb into dependents,
        or serialize via depends_on."""
        section = _readiness_section()
        self.assertIn("absorb", section.lower())
        self.assertIn("depends_on", section)


class TestReadinessChecklistMultiCommitCICheck(unittest.TestCase):
    """Acceptance bullet 3: CI handles multi-commit pushes. This is
    the runtime/infrastructure check that differentiates 'parallel
    runs work' from 'parallel runs work AND the CI pipeline doesn't
    choke on the resulting push'."""

    def test_check_bolded_and_phrased_exactly(self):
        section = _readiness_section()
        self.assertIn(
            "**Can CI handle multi-commit pushes?**",
            section,
            "CI check must be bolded with exact question wording",
        )

    def test_check_names_the_failure_mode(self):
        """The check must name what specifically happens during a
        parallel merge + push: multiple 'harness: merge <unit_id>'
        commits land in quick succession, then the orchestrator
        pushes them together. Without that framing, readers may
        interpret 'multi-commit pushes' as a normal git-workflow
        question rather than a parallelism-specific gate."""
        section = _readiness_section()
        self.assertIn("harness: merge", section,
                      "check must name the actual commit-message template")
        self.assertIn("push", section.lower())

    def test_check_names_concrete_ci_anti_patterns(self):
        """Authors need to know what to look for in their CI config.
        The check must name at least two concrete CI anti-patterns."""
        section = _readiness_section()
        self.assertIn("per-commit hooks", section.lower())
        # rate-limiting / status checks are a real Circle/Jenkins gotcha.
        self.assertIn("rate-limit", section.lower())

    def test_check_proposes_concrete_remediation(self):
        """If CI can't handle it, the check must tell the reader what
        to do (keep parallelism off)."""
        section = _readiness_section()
        self.assertIn("keep parallelism off until", section.lower())


class TestReadinessChecklistPreservesPreUnit051Items(unittest.TestCase):
    """The 8 original readiness items from unit_047 must survive the
    unit_051 edit. This is the regression guard -- a careless rewrite
    that replaces the list with the 3 new items would pass the new
    tests above but silently drop the pre-existing coverage."""

    def test_pre_existing_checklist_items_still_present(self):
        section = _readiness_section()
        # Shortened signatures of the pre-unit_051 items.
        for signature in (
            "3+ units that are genuinely independent",
            "overlap matrix won't reject legitimate pairs",
            "post-merge validator",
            "/harness-state",
            "git worktree add",
            "O_EXCL",
            "dogfooded at least one parallel batch",
        ):
            self.assertIn(
                signature, section,
                f"pre-unit_051 checklist item must survive the edit: "
                f"{signature!r}",
            )


if __name__ == "__main__":
    unittest.main()
