"""Tests for /harness-state doc coverage -- unit 042.

PHASE_010 observability requires the /harness-state rendered report to
cover three areas: (1) fleet state from state.execution.fleet, (2)
orphan worktrees from sync_harness.py, (3) per-batch timings from
.harness/logs/<batch_id>/. Both docs -- the long-form command at
skills/development-harness/commands/state.md and the workspace-commands
mirror at templates/workspace-commands/harness-state.md -- must carry
matching instructions so Claude Code and Cursor installs produce the
same report shape.

This test pins the contract at the doc level: heading presence, the
sync_harness.py reference, the three divergence categories, and the
exact timing line format so downstream tooling can parse it.
"""
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
LONG_DOC = SKILL_ROOT / "commands" / "state.md"
WORKSPACE_DOC = SKILL_ROOT / "templates" / "workspace-commands" / "harness-state.md"


class TestHarnessStateDocCoverage(unittest.TestCase):
    def _load(self, path):
        self.assertTrue(path.exists(), f"doc must exist: {path}")
        return path.read_text(encoding="utf-8")

    def test_both_docs_render_fleet_and_batch_section(self):
        """Both docs must instruct the agent to render a Fleet & Batch
        section that mirrors the checkpoint template's Batch block.
        Consumers cross-reference these two blocks, so the heading must
        match exactly.
        """
        for doc in (LONG_DOC, WORKSPACE_DOC):
            body = self._load(doc)
            self.assertIn(
                "## Fleet & Batch", body,
                f"{doc.name} output template must include a '## Fleet & Batch' section",
            )
            # Fleet state shape references.
            for needle in ("fleet.mode", "fleet.batch_id", "fleet.units"):
                self.assertIn(
                    needle, body,
                    f"{doc.name} must reference state.execution.{needle}",
                )

    def test_both_docs_render_orphans_section_via_sync_harness(self):
        """Both docs must instruct running sync_harness.py and rendering
        the three divergence categories. The Orphans section is never
        omitted -- absence of divergences is itself a reported fact.
        """
        for doc in (LONG_DOC, WORKSPACE_DOC):
            body = self._load(doc)
            self.assertIn(
                "sync_harness.py", body,
                f"{doc.name} must instruct running sync_harness.py for orphan detection",
            )
            self.assertIn(
                "## Orphans", body,
                f"{doc.name} output template must include an '## Orphans' section",
            )
            for category in ("orphan_worktree", "stale_fleet_entry", "orphan_branch"):
                self.assertIn(
                    category, body,
                    f"{doc.name} must name the '{category}' divergence category",
                )
            self.assertIn(
                "No orphans detected.", body,
                f"{doc.name} must specify the empty-divergences render "
                f"('No orphans detected.')",
            )

    def test_both_docs_specify_exact_timing_line_format(self):
        """Both docs must pin the one-line-per-batch format so
        downstream tooling can parse it:
            Batch <batch_id>: dispatched HH:MM:SS, merged HH:MM:SS, total Ns
        """
        timing_format = "Batch <batch_id>: dispatched HH:MM:SS, merged HH:MM:SS, total Ns"
        for doc in (LONG_DOC, WORKSPACE_DOC):
            body = self._load(doc)
            self.assertIn(
                "## Batch Timings", body,
                f"{doc.name} output template must include a '## Batch Timings' section",
            )
            self.assertIn(
                timing_format, body,
                f"{doc.name} must carry the exact timing-line format: {timing_format!r}",
            )
            self.assertIn(
                "Batch timings: unavailable", body,
                f"{doc.name} must specify the no-timings fallback render",
            )

    def test_both_docs_reference_dot_harness_logs_directory(self):
        """Per-batch timings are sourced from .harness/logs/<batch_id>/.
        The reader cue must be present so the agent knows where to look
        once unit_043 lands the directory layout.
        """
        for doc in (LONG_DOC, WORKSPACE_DOC):
            body = self._load(doc)
            self.assertIn(
                ".harness/logs/", body,
                f"{doc.name} must reference the .harness/logs/<batch_id>/ layout",
            )

    def test_docs_forbid_git_timestamp_inference_for_timings(self):
        """Batch timings must come from .harness/logs/, not from git
        commit timestamps. The docs must explicitly prohibit the
        fallback so an agent doesn't silently substitute git times when
        logs are missing.
        """
        for doc in (LONG_DOC, WORKSPACE_DOC):
            body = self._load(doc).lower()
            self.assertIn(
                "do not infer timings from git timestamps", body,
                f"{doc.name} must explicitly forbid git-timestamp inference for timings",
            )


if __name__ == "__main__":
    unittest.main()
