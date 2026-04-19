"""Tests for the checkpoint template shape -- unit 041.

PHASE_010 observability starts by rendering fleet state into the
human-readable checkpoint. The template at
skills/development-harness/templates/checkpoint-template.md is the
seed material for a new project's initial checkpoint.md (used by
commands/create.md). It must carry placeholders for the Batch section
so downstream tooling can fill them in.

No runtime script currently substitutes placeholders programmatically
-- they are filled in manually (or by the orchestrating agent) during
each invoke turn. This test pins the section's presence so a future
template edit cannot silently drop the Batch block.
"""
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT_TEMPLATE = SKILL_ROOT / "templates" / "checkpoint-template.md"


class TestCheckpointTemplateBatchSection(unittest.TestCase):
    def _load(self):
        self.assertTrue(
            CHECKPOINT_TEMPLATE.exists(),
            f"checkpoint-template.md must exist at {CHECKPOINT_TEMPLATE}",
        )
        return CHECKPOINT_TEMPLATE.read_text(encoding="utf-8")

    def test_batch_section_heading_present(self):
        body = self._load()
        self.assertIn(
            "## Batch (current or last)", body,
            "template must carry a 'Batch (current or last)' second-level heading",
        )

    def test_batch_section_placeholders_present(self):
        body = self._load()
        for placeholder in (
            "{{BATCH_ID_OR_NONE}}",
            "{{FLEET_MODE}}",
            "{{BATCH_UNIT_ROWS_OR_NONE}}",
            "{{BATCH_CONFLICTS_OR_NONE}}",
        ):
            self.assertIn(
                placeholder, body,
                f"Batch section must carry placeholder {placeholder}",
            )

    def test_batch_section_has_unit_table_columns(self):
        """The per-unit table must carry all columns needed to render
        state.execution.fleet.units without reshape: Unit, Phase, Status,
        Branch, Started, Ended. Missing a column forces the agent to
        reorganize the table on every render, which defeats templating.
        """
        body = self._load()
        header_line = next(
            (line for line in body.splitlines()
             if line.startswith("| Unit ") and "Status" in line),
            None,
        )
        self.assertIsNotNone(
            header_line,
            "Batch section must contain a markdown table header starting with | Unit ",
        )
        for column in ("Unit", "Phase", "Status", "Branch", "Started", "Ended"):
            self.assertIn(
                column, header_line,
                f"Batch unit table must carry a '{column}' column; got {header_line!r}",
            )

    def test_pre_existing_placeholders_still_present(self):
        """The Batch section is additive. All pre-PHASE_010 placeholders
        (LAST_COMPLETED_DESCRIPTION, etc.) must still exist so
        commands/create.md's initial-checkpoint step keeps working.
        """
        body = self._load()
        for placeholder in (
            "{{LAST_COMPLETED_DESCRIPTION}}",
            "{{FAILURES_OR_NONE}}",
            "{{NEXT_UNIT_DESCRIPTION}}",
            "{{BLOCKERS_OR_NONE}}",
            "{{EVIDENCE_SUMMARY}}",
            "{{QUESTIONS_OR_NONE}}",
            "{{TIMESTAMP}}",
        ):
            self.assertIn(
                placeholder, body,
                f"pre-existing placeholder {placeholder} must not be dropped "
                f"by the Batch-section addition",
            )


if __name__ == "__main__":
    unittest.main()
