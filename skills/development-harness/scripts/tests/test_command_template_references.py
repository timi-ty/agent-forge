"""Every template a command doc references must exist in the skill.

The harness commands copy files out of `templates/` into a user's
workspace. A reference to a template that is not present fails at
/create time -- in the user's project, after install -- and nothing in
this suite noticed, because no test enumerated those references.

That is exactly how `templates/rules/pr-review-checklist.md` came to be
required by commands/create.md, commands/invoke.md, schemas/manifest.json
and the workspace command while matching a broad `pr-*.md` ignore rule
and never being committed at all. The suite stayed green because every
template test hand-registers one specific file.

This test walks each `templates/...` reference in `commands/*.md` and
`templates/workspace-commands/*.md` and asserts it resolves, expanding
the two parameterisations create.md uses: the `[claude-code/]` tool fork
and the `$RULE_EXT` extension that goes with it. Running against a git
checkout is what makes it catch an ignored file -- present on the author's
disk, absent from the clone CI tests.

Prose references alone leave a hole: create.md names the workspace
commands only as a directory and then lists their destination filenames,
which carry no `templates/` prefix. All seven would rest on one
`is_dir()` check. So the second half of this test derives that inventory
from schemas/manifest.json, which declares every command the harness
deploys, and requires a source template for each.
"""
import json
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = SKILL_ROOT / "templates"
WORKSPACE_COMMANDS = TEMPLATES / "workspace-commands"
DOC_DIRS = (SKILL_ROOT / "commands", WORKSPACE_COMMANDS)
MANIFEST = SKILL_ROOT / "schemas" / "manifest.json"


# Matches a templates/... path wherever it appears: prose, a table cell, or
# either half of a markdown link. Stops at the first character that cannot be
# part of a path, so surrounding backticks and parens are excluded.
REFERENCE = re.compile(r"templates/[A-Za-z0-9_.*/$\[\]-]+")

# commands/create.md documents both tools in one row, e.g.
#   `templates/[claude-code/]rules/harness-core$RULE_EXT`
# Cursor reads templates/rules/*.mdc; Claude Code reads
# templates/claude-code/rules/*.md (create.md lines 299-300).
TOOL_FORKS = (("", ".mdc"), ("claude-code/", ".md"))


def _expand(ref):
    """Yield each concrete path a possibly-parameterised reference stands for."""
    if "[claude-code/]" in ref or "$RULE_EXT" in ref:
        for infix, ext in TOOL_FORKS:
            yield ref.replace("[claude-code/]", infix).replace("$RULE_EXT", ext)
    else:
        yield ref


def _scan():
    """Yield (doc, concrete_reference) for every template reference found."""
    for doc_dir in DOC_DIRS:
        for doc in sorted(doc_dir.glob("*.md")):
            body = doc.read_text(encoding="utf-8")
            for raw in REFERENCE.findall(body):
                # Trailing sentence punctuation, and the `]` that closes a
                # markdown link label -- no real reference ends in either.
                for ref in _expand(raw.rstrip(".,]")):
                    yield doc, ref


def _resolve(ref):
    """Return (exists, description) for one concrete reference."""
    rel = ref[len("templates/"):]
    if rel.endswith("/"):
        target = TEMPLATES / rel.rstrip("/")
        return target.is_dir(), f"directory {rel}"
    if "*" in rel:
        return bool(list(TEMPLATES.glob(rel))), f"glob {rel}"
    return (TEMPLATES / rel).is_file(), f"file {rel}"


class TestCommandTemplateReferences(unittest.TestCase):
    def test_every_referenced_template_resolves(self):
        """A command doc may not name a template the skill does not ship.

        Whatever /create is told to copy has to be there to copy.
        """
        missing = set()
        for doc, ref in _scan():
            exists, detail = _resolve(ref)
            if not exists:
                missing.add(f"{doc.name} -> {detail}")
        missing = sorted(missing)
        self.assertEqual(
            [], missing,
            "command docs reference templates that do not exist:\n  "
            + "\n  ".join(missing),
        )

    def test_scan_is_not_silently_empty(self):
        """Guard the scan itself.

        A regex that stops matching would make the test above pass by
        finding nothing, which is the failure mode it exists to prevent.
        """
        found = list(_scan())
        docs = {doc.name for doc, _ in found}
        self.assertGreaterEqual(
            len(found), 15,
            f"expected the docs to reference many templates, found {len(found)}",
        )
        self.assertGreaterEqual(
            len(docs), 2,
            f"expected references across several docs, found {sorted(docs)}",
        )

    def test_pr_review_checklist_template_is_present(self):
        """Named pin for the file this test was written after.

        commands/create.md copies it, commands/invoke.md and the workspace
        command gate phase completion on it, and schemas/manifest.json
        declares it. It went missing once; fail loudly if it goes again.
        """
        checklist = TEMPLATES / "rules" / "pr-review-checklist.md"
        self.assertTrue(
            checklist.is_file(),
            f"required by create.md, invoke.md and manifest.json: {checklist}",
        )


class TestWorkspaceCommandTemplates(unittest.TestCase):
    def test_every_manifest_command_has_a_source_template(self):
        """Each command the manifest deploys must have a template to copy.

        create.md points at the workspace-commands directory as a whole, so
        the reference scan above is satisfied by the directory existing --
        it cannot tell that six of the seven files went missing. The
        manifest is the authoritative list of what /create deploys, so
        derive the expectation from it rather than from prose.
        """
        entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
        commands = [e["path"] for e in entries if e.get("type") == "command"]
        self.assertTrue(commands, "manifest declares no command entries")

        missing = sorted(
            name for name in (Path(p).name for p in commands)
            if not (WORKSPACE_COMMANDS / name).is_file()
        )
        self.assertEqual(
            [], missing,
            "manifest declares commands with no source template in "
            f"{WORKSPACE_COMMANDS.name}/:\n  " + "\n  ".join(missing),
        )


if __name__ == "__main__":
    unittest.main()
