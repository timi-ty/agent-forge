"""Tests for ISSUE_001 fix -- unit_bugfix_001.

ISSUE_001: Stop hook fails to start on Windows where only 'python'
(not 'python3') is on PATH. skills/development-harness/commands/create.md
Phase 5 previously wrote a bare script path into the generated hook
configs ('.claude/settings.local.json' and '.cursor/hooks.json'),
relying on the hook script's '#!/usr/bin/env python3' shebang at
runtime. On Windows that shebang resolves 'env python3' -> exit 127
and Claude Code treats the failed hook as did-not-block, stopping
the invoke loop.

This test pins the fix at the doc level: create.md Phase 5 must
(a) apply the same 'PY=$(command -v python3 ...)' detection used by
every other entry point in the skill, and (b) bake the detected
interpreter into the generated hook 'command' field ('$PY .claude/
hooks/continue-loop.py' / '$PY .cursor/hooks/continue-loop.py')
with guidance to write the resolved absolute path into the JSON.

No runtime script substitutes these placeholders programmatically --
create.md is prose instructions interpreted by the bootstrapping
agent. The regression guard is therefore a doc-shape contract. If
a future edit reintroduces the bare-path template, this test trips
before the break ships.
"""
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
CREATE_DOC = SKILL_ROOT / "commands" / "create.md"


class TestCreateDocHookPythonDetection(unittest.TestCase):
    def _load(self):
        self.assertTrue(
            CREATE_DOC.exists(),
            f"create.md must exist at {CREATE_DOC}",
        )
        return CREATE_DOC.read_text(encoding="utf-8")

    def _hook_section(self, body):
        """Extract the '### Hook configuration' section body so
        assertions don't accidentally hit unrelated Python-detection
        snippets elsewhere in the doc."""
        start_marker = "### Hook configuration"
        self.assertIn(
            start_marker, body,
            f"{CREATE_DOC.name} must have a '### Hook configuration' section",
        )
        start = body.index(start_marker)
        # End at the next '### ' heading (next subsection of Phase 5).
        end = body.find("\n### ", start + len(start_marker))
        return body[start:end] if end != -1 else body[start:]

    def test_hook_section_applies_python_detection(self):
        body = self._load()
        section = self._hook_section(body)
        self.assertIn(
            'PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)',
            section,
            "Hook configuration section must apply the portable "
            "Python-detection idiom used by every other entry point",
        )

    def test_hook_section_bakes_py_into_claude_code_command(self):
        """The Claude Code hook command field must reference $PY so the
        resolved interpreter is baked into the generated JSON, not
        reliant on the hook script's shebang at runtime."""
        body = self._load()
        section = self._hook_section(body)
        self.assertIn(
            '"$PY .claude/hooks/continue-loop.py"',
            section,
            "Claude Code hook command must be '$PY .claude/hooks/"
            "continue-loop.py' so the detected interpreter is baked in",
        )

    def test_hook_section_bakes_py_into_cursor_command(self):
        """Mirror assertion for Cursor."""
        body = self._load()
        section = self._hook_section(body)
        self.assertIn(
            '"$PY .cursor/hooks/continue-loop.py"',
            section,
            "Cursor hook command must be '$PY .cursor/hooks/"
            "continue-loop.py' so the detected interpreter is baked in",
        )

    def test_hook_section_forbids_bare_script_path_for_command(self):
        """Explicit negative check: the pre-fix bare-path command
        must not reappear. A regex check would over-match our own
        guidance text ('Write the actual path into the JSON; do not
        leave the literal $PY'); we guard the specific bare-path
        JSON tokens instead.
        """
        body = self._load()
        section = self._hook_section(body)
        for forbidden in (
            '"command": ".claude/hooks/continue-loop.py"',
            '"command": ".cursor/hooks/continue-loop.py"',
        ):
            self.assertNotIn(
                forbidden, section,
                f"Hook section must not carry the pre-fix bare-path "
                f"command template: {forbidden!r}",
            )

    def test_hook_section_instructs_resolving_py_placeholder(self):
        """The literal '$PY' must not be written into the generated
        JSON on disk -- the doc must instruct writing the resolved
        absolute path. Pin that guidance so a reader doesn't
        misinterpret the JSON snippets as copy-paste-ready templates
        with an unresolved placeholder.
        """
        body = self._load()
        section = self._hook_section(body)
        self.assertIn(
            "do not leave the literal `$PY` in the file", section,
            "Hook configuration must instruct resolving $PY to the "
            "absolute path before writing the JSON",
        )


if __name__ == "__main__":
    unittest.main()
