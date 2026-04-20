"""Tests for the self-test fixture -- unit_054.

PHASE_013 harness-self-test starts by creating a throwaway
workspace the harness will be run against to validate end-to-end
behavior. This module pins the fixture's existence + the seeded-
conditions contract documented in README.md: batch >= 2, overlap-
matrix rejection, and scope violation.

The fixture itself is consumed ad-hoc (not by CI); these tests are
a structural presence + doc-shape contract ensuring the fixture
stays consistent with the PHASE_013 acceptance criteria and with
the downstream units (055-058) that will run against it.
"""
import unittest
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "self-test"
ROADMAP = FIXTURE_DIR / "ROADMAP.md"
README = FIXTURE_DIR / "README.md"


class TestFixtureFilesExist(unittest.TestCase):
    def test_fixture_directory_present(self):
        self.assertTrue(
            FIXTURE_DIR.is_dir(),
            f"self-test fixture directory must exist at {FIXTURE_DIR}",
        )

    def test_roadmap_present(self):
        self.assertTrue(
            ROADMAP.is_file(),
            f"ROADMAP.md must exist at {ROADMAP}",
        )

    def test_readme_present(self):
        self.assertTrue(
            README.is_file(),
            f"README.md must exist at {README}",
        )


class TestRoadmapShape(unittest.TestCase):
    """The roadmap must describe the two-milestone structure the
    downstream units (055-058) expect. Without this shape, the
    compiled phase graph won't produce the seeded conditions."""

    def _read(self):
        return ROADMAP.read_text(encoding="utf-8")

    def test_roadmap_names_two_milestones(self):
        body = self._read()
        self.assertIn("### Items", body,
                      "ROADMAP must have an Items milestone heading")
        self.assertIn("### Users", body,
                      "ROADMAP must have a Users milestone heading")

    def test_roadmap_describes_fixture_role(self):
        """The roadmap is a harness self-test fixture, not a real
        product. It must say so to avoid confusing future readers."""
        body = self._read().lower()
        self.assertIn("self-test fixture", body,
                      "ROADMAP must identify itself as a harness self-test fixture")


class TestReadmeDocumentsAllThreeSeededConditions(unittest.TestCase):
    """The README is the binding contract between unit_054 and
    downstream units 055-058. Each seeded condition (batch >= 2,
    overlap rejection, scope violation) must be documented with its
    specific unit id + expected mechanism so the downstream operator
    recipe is actionable."""

    def _read(self):
        return README.read_text(encoding="utf-8")

    def test_documents_batch_ge_2(self):
        body = self._read()
        self.assertIn("Batch ≥ 2", body,
                      "README must document the 'Batch >= 2' seeded condition")
        # Must name which units form the batch + what's excluded.
        self.assertIn("unit_a1", body)
        self.assertIn("unit_a2", body)

    def test_documents_overlap_rejection(self):
        """The path_overlap_with:<id> exclusion is the exact string
        compute_parallel_batch.py emits; pin it here so operators
        running the self-test know what to look for in batch.json."""
        body = self._read()
        self.assertIn("Overlap-matrix rejection", body)
        self.assertIn("path_overlap_with:unit_a2", body,
                      "README must name the exact exclusion-reason string "
                      "that unit_a3 will produce")
        # Must explain WHY this is the harness's seeded 'merge conflict'
        # (the phase doc uses the term loosely).
        self.assertIn("would merge-conflict", body.lower())

    def test_documents_scope_violation(self):
        body = self._read()
        self.assertIn("Scope violation", body)
        self.assertIn("unit_b2", body,
                      "README must name which unit will produce the scope violation")
        # Must name the file outside scope + the conflict category that
        # _scope_violations emits.
        self.assertIn("src/seeds/users.json", body)
        self.assertIn('conflict.category: "scope_violation"', body)


class TestReadmeLinksToDownstreamArtifacts(unittest.TestCase):
    """Units 055-058 will create additional artifacts (phase-graph,
    config, trace, post-mortem) in this same directory. The README
    must forward-reference them so readers know the fixture is
    incomplete until the full PHASE_013 arc finishes."""

    def _read(self):
        return README.read_text(encoding="utf-8")

    def test_mentions_planned_artifacts(self):
        body = self._read()
        for artifact in ("phase-graph.json", "config.json", "trace.log", "POST-MORTEM.md"):
            self.assertIn(
                artifact, body,
                f"README must forward-reference {artifact} (created by "
                f"units 055-058)",
            )

    def test_declares_expected_end_state_after_full_run(self):
        """An operator running the self-test must know when to stop --
        the README must specify the expected post-run state so 'done'
        is a concrete observation, not a vibe check."""
        body = self._read().lower()
        self.assertIn("expected end state", body)
        # Orphan-free is a specific invariant the operator must verify.
        self.assertIn("no orphaned worktrees", body)
        self.assertIn("no orphaned branches", body)


class TestFixtureIsolatedFromRegularTests(unittest.TestCase):
    """The fixture is ad-hoc operator material, NOT a unittest target.
    Verify that no accidental unittest discovery happens against the
    fixture directory."""

    def test_fixture_has_no_test_modules(self):
        """Any file named test_*.py inside fixtures/ would be picked
        up by unittest discover and cause false positives. Fixture
        stays prose-only."""
        for path in FIXTURE_DIR.rglob("test_*.py"):
            self.fail(
                f"fixture must not contain test_*.py modules (ad-hoc "
                f"fixture, not CI); found {path}"
            )


if __name__ == "__main__":
    unittest.main()
