"""Tests for the 'Version upgrades' section in SKILL.md -- unit_052.

PHASE_012 release-readiness requires SKILL.md to document the
version-upgrade path explicitly so users who hit a schema mismatch
have a clear next action. The acceptance criterion from the phase
doc is 'Paragraph present; explicitly states \"no migration script
is provided by design\" and points to /create-development-harness'.

This test module pins each substantive claim in the new section so
a future edit cannot silently weaken the upgrade guidance.
"""
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_ROOT / "SKILL.md"


def _load():
    assert SKILL_MD.exists(), f"SKILL.md must exist at {SKILL_MD}"
    return SKILL_MD.read_text(encoding="utf-8")


def _section():
    body = _load()
    heading = "## Version upgrades"
    assert heading in body, f"SKILL.md must contain '{heading}'"
    start = body.index(heading)
    end = body.find("\n## ", start + len(heading))
    return body[start:end] if end != -1 else body[start:]


class TestVersionUpgradesSectionPresent(unittest.TestCase):
    def test_section_heading_present(self):
        body = _load()
        self.assertIn("## Version upgrades", body,
                      "SKILL.md must have a 'Version upgrades' section")

    def test_section_placed_before_key_principle(self):
        """Position matters -- the section must come BEFORE 'Key
        Principle' so a reader encountering the schema-mismatch error
        in practice reads the upgrade path before the closing
        philosophical summary. A section placed after Key Principle
        would be more likely to be skipped."""
        body = _load()
        idx_version = body.find("## Version upgrades")
        idx_key = body.find("## Key Principle")
        self.assertNotEqual(idx_version, -1)
        self.assertNotEqual(idx_key, -1)
        self.assertLess(
            idx_version, idx_key,
            "Version upgrades section must come before Key Principle",
        )


class TestVersionUpgradesSubstantiveClaims(unittest.TestCase):
    """Four substantive claims must survive any future edit:
      1. Re-run /create-development-harness.
      2. ROADMAP.md + PHASES/*.md are preserved.
      3. No migration script is provided by design.
      4. Points at config.execution_mode.versioning.break_on_schema_bump
         as the config knob.
    """

    def test_instructs_rerun_create(self):
        section = _section()
        self.assertIn(
            "/create-development-harness", section,
            "Version upgrades must point users at /create-development-harness",
        )
        # The first numbered step must be 'Re-run', not some paraphrase.
        self.assertIn("Re-run", section,
                      "upgrade path must lead with 'Re-run' as the action")

    def test_preserves_roadmap_and_phases(self):
        """This is the claim that makes the upgrade path palatable --
        the ROADMAP and PHASES docs represent real product/planning
        work that users don't want to re-author. Pin that they
        survive the recreate flow."""
        section = _load()
        # Section must state both files survive.
        self.assertIn("ROADMAP.md", section,
                      "Version upgrades must name ROADMAP.md as preserved")
        self.assertIn("PHASES/*.md", section,
                      "Version upgrades must name PHASES/*.md as preserved")
        self.assertIn("preserved", section.lower())

    def test_states_no_migration_script_by_design(self):
        """The exact-wording 'no migration script is provided by design'
        phrase is pinned by the phase doc's acceptance criterion. This
        is the claim that signals intentionality -- without 'by design',
        users might interpret the absence as a gap waiting for a
        future migration tool."""
        section = _section()
        self.assertIn(
            "no migration script is provided by design",
            section.lower(),
            "Version upgrades must state 'no migration script is "
            "provided by design' verbatim (lowercase match)",
        )

    def test_explains_why_no_migration(self):
        """A bare 'by design' without justification invites 'why
        not?' bug reports. The section must name the cost argument:
        a reliable general-purpose migration is more expensive than
        re-generation given ROADMAP + PHASES as preserved inputs."""
        section = _section()
        section_lower = section.lower()
        # Must articulate the cost/benefit argument.
        self.assertIn("cost", section_lower,
                      "Version upgrades must explain the cost argument for "
                      "no migration script")

    def test_names_break_on_schema_bump_config(self):
        """The config knob config.execution_mode.versioning.
        break_on_schema_bump is what operationalizes the policy.
        Pin its presence so a reader finding the section knows
        exactly which config field enforces the default."""
        section = _section()
        self.assertIn(
            "config.execution_mode.versioning.break_on_schema_bump",
            section,
            "Version upgrades must name the config knob that enforces "
            "the break-on-bump default",
        )
        # The default value must be called out.
        self.assertIn("true", section,
                      "Version upgrades must state break_on_schema_bump is "
                      "the default (true)")


class TestVersionUpgradesListsRegeneratedFiles(unittest.TestCase):
    """Bonus coverage: the section distinguishes what gets
    regenerated from what survives. This matters because users may
    have hand-edited some of the regenerated files (hook scripts,
    rule files) and need to know those edits will be lost."""

    def test_section_lists_regenerated_files(self):
        section = _section()
        # At minimum the regenerated set must include the core state
        # files + scripts directory.
        for regenerated in (
            "state.json",
            "phase-graph.json",
            "checkpoint.md",
            "manifest.json",
        ):
            self.assertIn(
                regenerated, section,
                f"Version upgrades must name {regenerated} as regenerated "
                f"so users know hand-edits will be lost",
            )


if __name__ == "__main__":
    unittest.main()
