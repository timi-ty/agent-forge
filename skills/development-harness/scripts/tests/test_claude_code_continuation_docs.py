"""Tests for ISSUE_002 doc-level regression guards -- unit_bugfix_002.

ISSUE_002: Claude Code Stop-hook continuation is a one-shot guard;
the harness's auto-continue design is a direct Cursor port and is
structurally incompatible with Claude Code's Stop hook protocol. The
fix retires the block-continue driver on Claude Code and moves
autonomous multi-turn runs to the native ``/loop`` skill.

This module pins the documentation contract at the doc level:

1. commands/create.md Phase 5 (Hook configuration) must describe the
   Claude Code hook as a precondition checker, not a continuation
   driver. The pre-fix 'block stopping' / 'exit 2' language must not
   reappear.
2. commands/invoke.md and templates/workspace-commands/invoke-
   development-harness.md must carry a 'Claude Code: run under /loop'
   section pointing users at '/loop /invoke-development-harness' as
   the autonomous-run entry point.
3. references/claude-code-continuation.md must exist and document the
   protocol mismatch and the two-track fix (Claude Code precondition-
   only; Cursor unchanged).
"""
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
CREATE_DOC = SKILL_ROOT / "commands" / "create.md"
INVOKE_LONG_DOC = SKILL_ROOT / "commands" / "invoke.md"
INVOKE_WORKSPACE_DOC = SKILL_ROOT / "templates" / "workspace-commands" / "invoke-development-harness.md"
CONTINUATION_REF = SKILL_ROOT / "references" / "claude-code-continuation.md"


def _read(path):
    assert path.exists(), f"doc must exist: {path}"
    return path.read_text(encoding="utf-8")


class TestCreateDocClaudeCodeHookRole(unittest.TestCase):
    """create.md Phase 5's Claude Code branch must describe the hook
    as a precondition checker, not a block-continue driver."""

    def _claude_code_hook_block(self, body):
        """Slice out the '**If $TOOL is claude-code:**' subsection of
        Phase 5 Hook configuration so assertions do not leak into the
        Cursor block or other sections."""
        start_token = "**If `$TOOL` is `claude-code`:**"
        self.assertIn(
            start_token, body,
            "create.md Phase 5 must have a '**If `$TOOL` is `claude-code`:**' subsection",
        )
        start = body.index(start_token)
        # End at the next '###' heading (next Phase-5 subsection).
        end = body.find("\n### ", start + len(start_token))
        return body[start:end] if end != -1 else body[start:]

    def test_claude_code_branch_names_precondition_checker_role(self):
        body = _read(CREATE_DOC)
        section = self._claude_code_hook_block(body)
        self.assertIn(
            "precondition checker", section,
            "Claude Code hook-configuration subsection must describe the "
            "hook as a 'precondition checker'",
        )

    def test_claude_code_branch_negates_block_continue_behavior(self):
        """The section must explicitly say the hook does NOT block-
        continue -- a positive check for the negating phrase. This is
        how we guard against regression: a future rewrite that describes
        the hook as a continuation driver would have to keep or replace
        this negating phrase, and a simple deletion would trip the
        assertion.
        """
        body = _read(CREATE_DOC)
        section = self._claude_code_hook_block(body)
        self.assertIn(
            "always exits 0", section,
            "Claude Code Phase-5 subsection must state the hook 'always "
            "exits 0' (no exit-2 block-continue)",
        )
        self.assertIn(
            "does NOT emit", section,
            "Claude Code Phase-5 subsection must carry a 'does NOT emit' "
            "callout against block-continue behavior",
        )

    def test_claude_code_branch_points_at_loop_skill(self):
        body = _read(CREATE_DOC)
        section = self._claude_code_hook_block(body)
        self.assertIn(
            "/loop", section,
            "Claude Code hook-configuration subsection must point users at "
            "the /loop skill for autonomous multi-turn runs",
        )

    def test_claude_code_branch_links_continuation_reference(self):
        """The subsection must link the new reference doc so future
        readers can chase the why."""
        body = _read(CREATE_DOC)
        section = self._claude_code_hook_block(body)
        self.assertIn(
            "claude-code-continuation.md", section,
            "Claude Code hook-configuration subsection must link the "
            "claude-code-continuation.md reference",
        )


class TestInvokeDocsLoopSection(unittest.TestCase):
    """Both invoke docs must carry a 'Claude Code: run under /loop'
    section pointing users at '/loop /invoke-development-harness' as
    the autonomous-run primitive on Claude Code."""

    DOCS = (INVOKE_LONG_DOC, INVOKE_WORKSPACE_DOC)

    def test_both_docs_have_claude_code_loop_heading(self):
        for doc in self.DOCS:
            body = _read(doc)
            self.assertIn(
                "Claude Code: run under `/loop`", body,
                f"{doc.name} must have a 'Claude Code: run under `/loop`' section",
            )

    def test_both_docs_name_loop_invoke_development_harness(self):
        for doc in self.DOCS:
            body = _read(doc)
            self.assertIn(
                "/loop /invoke-development-harness", body,
                f"{doc.name} must tell Claude Code users to run "
                f"'/loop /invoke-development-harness'",
            )

    def test_both_docs_note_one_batch_per_turn_on_claude_code(self):
        """The doc must call out that direct /invoke-development-harness
        runs exactly one batch per turn on Claude Code -- sets
        expectations so users don't wait for an auto-continue that never
        comes."""
        for doc in self.DOCS:
            body = _read(doc).lower()
            self.assertIn(
                "one batch per turn", body,
                f"{doc.name} must call out 'one batch per turn' behavior "
                f"on Claude Code",
            )

    def test_both_docs_note_cursor_is_unchanged(self):
        """Reassurance for Cursor users that this change does not
        affect them. Avoids spurious bug reports from Cursor users
        wondering why their continuation model suddenly shifted."""
        for doc in self.DOCS:
            body = _read(doc).lower()
            self.assertIn(
                "cursor",
                body,
                f"{doc.name} must mention Cursor to contrast behavior",
            )
            self.assertTrue(
                "cursor is unchanged" in body or "cursor installs are unchanged" in body,
                f"{doc.name} must explicitly state Cursor is unchanged; "
                f"body did not contain a 'cursor ... unchanged' claim",
            )


class TestClaudeCodeContinuationReferenceExists(unittest.TestCase):
    """The new reference doc must exist and carry the substantive
    claims the rest of the fix relies on."""

    def test_reference_doc_exists(self):
        self.assertTrue(
            CONTINUATION_REF.exists(),
            f"references/claude-code-continuation.md must exist at {CONTINUATION_REF}",
        )

    def test_reference_explains_protocol_mismatch(self):
        body = _read(CONTINUATION_REF)
        # Must name both protocols explicitly.
        self.assertIn("stop_hook_active", body,
                      "reference must name the Claude Code guard")
        self.assertIn("followup_message", body,
                      "reference must name the Cursor protocol")

    def test_reference_documents_two_track_fix(self):
        body = _read(CONTINUATION_REF)
        self.assertIn(
            "precondition-only", body,
            "reference must describe the Claude Code hook's new "
            "precondition-only role",
        )
        self.assertIn(
            "/loop /invoke-development-harness", body,
            "reference must point at /loop as the autonomous-run primitive",
        )

    def test_reference_marks_cursor_as_unchanged(self):
        body = _read(CONTINUATION_REF).lower()
        self.assertIn(
            "cursor", body,
            "reference must discuss Cursor explicitly",
        )
        self.assertIn(
            "unchanged", body,
            "reference must state Cursor is unchanged",
        )


if __name__ == "__main__":
    unittest.main()
