"""Tests for the /update-development-harness schema-mismatch precheck
-- unit_053.

PHASE_012 release-readiness requires /update-development-harness
to detect a schema_version mismatch between the installed .harness/
and the installed skill, emit a pointer to /create-development-
harness, and NOT attempt in-place migration.

This module covers both sides of the acceptance criterion:
  (1) The v1-fixture user-flow assertion: wrap validate_harness.py
      (what the update command now runs as its Step 0.5 precheck)
      and verify it produces the actionable re-create pointer on
      v1 input.
  (2) The doc-shape contract: both commands/update.md and
      templates/workspace-commands/update-development-harness.md
      carry the precheck step + the refusal language + the 'no
      migration script is provided by design' cross-link.

Paired with test_validate_harness.py (PHASE_001 unit_006) which
pins the validator's rejection behavior at the validator level;
this module pins the behavior at the /update command level.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
SKILL_ROOT = SCRIPT_DIR.parent
VALIDATE_SCRIPT = SCRIPT_DIR / "validate_harness.py"
UPDATE_DOC = SKILL_ROOT / "commands" / "update.md"
UPDATE_WORKSPACE = SKILL_ROOT / "templates" / "workspace-commands" / "update-development-harness.md"


def _run_validate(root):
    """Run validate_harness.py against a fixture root and return
    (returncode, parsed stdout JSON). Matches the exact invocation
    commands/update.md Step 0.5 instructs."""
    result = subprocess.run(
        [sys.executable, str(VALIDATE_SCRIPT), "--root", str(root)],
        capture_output=True, text=True, cwd=str(SCRIPT_DIR),
    )
    try:
        output = json.loads(result.stdout) if result.stdout else {}
    except json.JSONDecodeError:
        output = {}
    return result.returncode, output


def _v1_json(base):
    return {**base, "schema_version": "1.0"}


class TestV1FixtureTripsSchemaMismatch(unittest.TestCase):
    """End-to-end user flow: a project bootstrapped under v1 and
    then left alone while the skill bumped to v2 should produce an
    actionable re-create pointer when the user types
    /update-development-harness. This wraps validate_harness.py
    directly because that is exactly what the update command's
    Step 0.5 invokes."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True)
        )

    def _seed_v1_workspace(self):
        """Minimal v1-shaped harness workspace. Just enough to make
        validate_harness reach the schema check."""
        harness_dir = self.temp_dir / ".harness"
        harness_dir.mkdir()

        config = _v1_json({
            "project": {"name": "test", "description": ""},
            "stack": {}, "deployment": {}, "git": {}, "testing": {}, "quality": {},
        })
        state = _v1_json({"execution": {}, "checkpoint": {}})
        manifest = _v1_json({
            "entries": [
                {"path": "PHASES/", "ownership": "harness-owned",
                 "type": "directory", "removable": True},
            ],
        })
        phase_graph = _v1_json({
            "phases": [
                {"id": "PHASE_001", "slug": "p1", "status": "pending",
                 "depends_on": [], "units": []}
            ],
        })

        (harness_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        (harness_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        (harness_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (harness_dir / "phase-graph.json").write_text(json.dumps(phase_graph, indent=2), encoding="utf-8")
        (harness_dir / "checkpoint.md").write_text("# Checkpoint\n", encoding="utf-8")
        (self.temp_dir / "PHASES").mkdir()
        return self.temp_dir

    def test_v1_fixture_produces_recreate_pointer(self):
        """The exact user observation: typing /update-development-
        harness on a v1 harness must surface '/create-development-
        harness' in the validator's error output. Asserts both the
        returncode and the pointer-substring the update-doc relies on."""
        root = self._seed_v1_workspace()
        returncode, output = _run_validate(root)

        self.assertEqual(
            returncode, 1,
            f"validator must exit 1 for v1 schema; got {returncode} "
            f"with output={output!r}",
        )
        self.assertFalse(
            output.get("valid"),
            "valid flag must be False for v1 schema",
        )
        joined_errors = " ".join(output.get("errors", []))
        self.assertIn(
            "/create-development-harness", joined_errors,
            "v1-fixture validator output must point at "
            "/create-development-harness so the update doc's Step 0.5 "
            "branch surfaces the correct message",
        )

    def test_v1_all_four_json_files_referenced_in_errors(self):
        """The validator's error output must name each of the 4 JSON
        files whose schema_version is wrong, so the update command can
        tell the user exactly which files will be regenerated by the
        recreate flow."""
        root = self._seed_v1_workspace()
        _returncode, output = _run_validate(root)
        joined_errors = " ".join(output.get("errors", []))
        for filename in ("config.json", "state.json", "manifest.json", "phase-graph.json"):
            self.assertIn(
                filename, joined_errors,
                f"validator error output must name {filename!r} "
                f"for v1 fixtures",
            )


class TestUpdateDocsCarryPrecheckContract(unittest.TestCase):
    """Both /update-development-harness docs must instruct running
    validate_harness.py as a precheck AND carry the refusal language
    when the validator points at /create-development-harness."""

    DOCS = (UPDATE_DOC, UPDATE_WORKSPACE)

    def _read(self, path):
        self.assertTrue(path.exists(), f"doc must exist: {path}")
        return path.read_text(encoding="utf-8")

    def test_both_docs_have_schema_precheck_step(self):
        """Long-form update.md uses 'Step 0' and the workspace mirror
        uses 'Step 0.5' because Cursor's template already carries a
        'Step 0: Resolve tool paths'. Either heading shape satisfies
        the contract -- it just has to exist before the procedure."""
        for doc in self.DOCS:
            body = self._read(doc)
            self.assertTrue(
                "Schema Version Precheck" in body or "Schema Version precheck" in body,
                f"{doc.name} must have a 'Schema Version Precheck' section",
            )

    def test_both_docs_name_validate_harness_as_the_precheck_tool(self):
        for doc in self.DOCS:
            body = self._read(doc)
            self.assertIn(
                "validate_harness.py", body,
                f"{doc.name} precheck must invoke validate_harness.py",
            )

    def test_both_docs_instruct_surfacing_recreate_pointer(self):
        """On exit-1 with the pointer in output, the doc must tell
        the agent to surface '/create-development-harness' to the
        user. Without this wording the precheck is useless -- the
        agent would detect the mismatch but not act on it."""
        for doc in self.DOCS:
            body = self._read(doc)
            self.assertIn("/create-development-harness", body)
            # Must tell the reader the mismatch maps to 'older schema'
            # -- the signal users can act on.
            self.assertIn("older schema", body.lower())

    def test_both_docs_state_no_migration_script_by_design(self):
        """The doc must repeat the 'no migration script is provided
        by design' line so the agent surfacing the advisory doesn't
        imply future migration tooling is coming."""
        for doc in self.DOCS:
            body = self._read(doc).lower()
            self.assertIn(
                "no migration script is provided by design", body,
                f"{doc.name} must repeat the 'no migration script is "
                f"provided by design' policy line verbatim",
            )

    def test_both_docs_cross_link_skill_md_version_upgrades(self):
        """The cost rationale lives in SKILL.md § 'Version upgrades'
        (unit_052). The update docs must cross-link it so readers
        can chase the 'why'."""
        for doc in self.DOCS:
            body = self._read(doc)
            self.assertIn("SKILL.md", body,
                          f"{doc.name} must link to SKILL.md")
            self.assertIn("Version upgrades", body,
                          f"{doc.name} must name the 'Version upgrades' section")

    def test_both_docs_forbid_in_place_migration(self):
        """The explicit 'Do NOT attempt in-place migration' instruction
        is load-bearing -- without it, a well-meaning agent might try
        to edit schema_version values by hand on a v1 harness."""
        for doc in self.DOCS:
            body = self._read(doc)
            self.assertIn("Do NOT attempt", body,
                          f"{doc.name} must explicitly forbid in-place migration "
                          "with 'Do NOT attempt' wording")

    def test_long_doc_removed_schema_migration_category(self):
        """The pre-unit_053 Categorize-the-Change table had a 'Schema
        migration' row. That row must be gone -- schema_version bumps
        are no longer a category, they trigger the precheck rejection."""
        body = self._read(UPDATE_DOC)
        self.assertNotIn(
            "| **Schema migration** |", body,
            "update.md must no longer list 'Schema migration' as a "
            "change category",
        )
        # An explanation that schema bumps aren't a category should be
        # present so the reader sees what replaced the deleted row.
        self.assertIn("schema_version` bumps are NOT a category", body)


if __name__ == "__main__":
    unittest.main()
