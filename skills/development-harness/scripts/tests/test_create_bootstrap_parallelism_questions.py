"""Tests for the create.md bootstrap flow additions -- unit_048.

PHASE_011's final unit extends two sections of commands/create.md:

  * Phase 2 (Ask Questions) gains an 'Execution Mode' category with
    two structured questions -- exact verbatim wording is required
    so every install produces the same config shape:
      1. 'Enable parallel unit execution? (y/n, default n)' ->
         config.execution_mode.parallelism.enabled
      2. 'Break-on-schema-bump vs migrate? (break/migrate, default
         break)' -> config.execution_mode.versioning.break_on_schema_bump

  * Phase 4 Step 2 (Interrogate and refine each phase) gains
    depends_on / parallel_safe / touches_paths as required unit
    fields + a 'Parallelism-by-default' paragraph that instructs
    the agent to propose parallel_safe: true where safe and
    parallel_safe: false when blast radius is unknown.

No runtime script programmatically interprets these prompts -- they
are prose the agent bootstrapping a new project follows. The
regression guard is therefore a doc-shape contract. Pins the verbatim
question strings AND the default answers AND the downstream config
paths so a future edit can't silently drop coverage.
"""
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
CREATE_DOC = SKILL_ROOT / "commands" / "create.md"


def _read():
    assert CREATE_DOC.exists(), f"create.md must exist at {CREATE_DOC}"
    return CREATE_DOC.read_text(encoding="utf-8")


def _slice(body, start_marker, next_marker="## Phase "):
    """Slice from start_marker up to the next '## Phase ' heading so
    per-section assertions don't leak across phases."""
    assert start_marker in body, f"expected marker not found: {start_marker!r}"
    start = body.index(start_marker)
    end = body.find("\n" + next_marker, start + len(start_marker))
    return body[start:end] if end != -1 else body[start:]


class TestPhase2ExecutionModeQuestions(unittest.TestCase):
    """Phase 2 must carry an 'Execution Mode' category with the two
    structured questions in their verbatim shape."""

    def _phase2(self):
        return _slice(_read(), "## Phase 2: Ask Questions")

    def test_execution_mode_category_heading(self):
        section = self._phase2()
        self.assertIn("**Execution Mode**", section,
                      "Phase 2 must have an 'Execution Mode' category")

    def test_parallelism_question_verbatim(self):
        """The y/n/default-n wording is load-bearing -- the generated
        config.execution_mode.parallelism.enabled is a boolean, and
        the prompt shape tells the agent exactly how to map answers."""
        section = self._phase2()
        self.assertIn(
            "`Enable parallel unit execution? (y/n, default n)`",
            section,
            "parallelism question must be verbatim (backtick-quoted)",
        )
        # Answer-to-value mapping must be explicit so the agent doesn't
        # guess at truthiness.
        self.assertIn("`true`", section)
        self.assertIn("`false` (default)", section)

    def test_parallelism_question_maps_to_config_path(self):
        section = self._phase2()
        self.assertIn(
            "config.execution_mode.parallelism.enabled", section,
            "parallelism question must name its config target path",
        )
        # The full parallelism block must be called out (not just the
        # enabled flag) so the generated config is self-documenting.
        for field in (
            "max_concurrent_units",
            "conflict_strategy",
            "require_touches_paths",
            "allow_cross_phase",
        ):
            self.assertIn(
                field, section,
                f"parallelism question must name the '{field}' sub-field "
                f"so the full config block is generated on yes-answer",
            )

    def test_parallelism_question_points_at_readiness_checklist(self):
        """On a 'y' answer, the bootstrap agent must warn the user to
        consult the readiness checklist (unit_047's parallel-
        execution.md) -- that's where 'do you actually need this?' is
        operationalized."""
        section = self._phase2()
        self.assertIn("parallel-execution.md", section)
        self.assertIn("Readiness checklist", section)

    def test_schema_bump_question_verbatim(self):
        section = self._phase2()
        self.assertIn(
            "`Break-on-schema-bump vs migrate? (break/migrate, default break)`",
            section,
            "schema-bump question must be verbatim",
        )

    def test_schema_bump_question_maps_to_config_path(self):
        section = self._phase2()
        self.assertIn(
            "config.execution_mode.versioning.break_on_schema_bump",
            section,
            "schema-bump question must name its config target path",
        )
        # Answer mapping must be explicit (break -> true, migrate -> false).
        self.assertIn("`break`", section)
        self.assertIn("`migrate`", section)
        self.assertIn("`/create-development-harness`", section,
                      "schema-bump explanation must name the recover path "
                      "for break-on-bump scenarios")

    def test_exact_wording_note_before_questions(self):
        """The 'use exact wording' note is what makes these questions
        stable across installs. Without it, the agent may paraphrase
        and break the regression contract."""
        section = self._phase2()
        self.assertIn("use exact wording", section,
                      "Execution Mode category must note that wording is "
                      "verbatim so config shapes are consistent")


class TestPhase4UnitFieldsAddParallelismTriple(unittest.TestCase):
    """Phase 4 Step 2's unit-field list must grow from 4 fields to 7
    (adding depends_on, parallel_safe, touches_paths)."""

    def _phase4(self):
        return _slice(_read(), "## Phase 4: Compile Roadmap into Phases")

    def test_step2_covers_depends_on(self):
        section = self._phase4()
        self.assertIn("`depends_on`:", section,
                      "Phase 4 Step 2 must list depends_on as a required unit field")

    def test_step2_covers_parallel_safe_with_default_false_guidance(self):
        section = self._phase4()
        self.assertIn("`parallel_safe`:", section)
        # Acceptance criterion: 'setting parallel_safe: false when blast
        # radius is unknown'. Must be explicit in the prose.
        self.assertIn("blast radius", section.lower(),
                      "parallel_safe guidance must name 'blast radius'")
        self.assertTrue(
            "Default to `false`" in section or "default to false" in section.lower(),
            "parallel_safe guidance must default to false on unknown blast radius",
        )

    def test_step2_covers_touches_paths_proposal_instruction(self):
        """Acceptance bullet: 'Phase 4 to instruct proposing
        touches_paths per unit'. The prose must explicitly direct the
        agent to propose these at unit-authoring time."""
        section = self._phase4()
        self.assertIn("`touches_paths`:", section)
        self.assertIn("Propose this", section,
                      "touches_paths guidance must instruct the agent to "
                      "propose globs proactively")
        self.assertIn("narrower globs", section,
                      "touches_paths guidance must prefer narrower globs")

    def test_step2_has_parallelism_by_default_subsection(self):
        """The 'Parallelism-by-default' block activates when config
        turns parallelism on. Pin its presence + the dry-run command."""
        section = self._phase4()
        self.assertIn("Parallelism-by-default", section)
        self.assertIn("select_next_unit.py --frontier", section)
        self.assertIn("compute_parallel_batch.py", section)
        # Must cross-link to the scope-violation framing so readers
        # understand why touches_paths disjointness matters.
        self.assertIn("path_overlap_with", section,
                      "parallelism-by-default must name the exclusion reason "
                      "so dry-run output is self-explanatory")


if __name__ == "__main__":
    unittest.main()
