"""Tests for the self-test fixture -- units 054 + 055.

PHASE_013 harness-self-test starts by creating a throwaway
workspace the harness will be run against to validate end-to-end
behavior. This module pins:

  * unit_054: fixture exists (ROADMAP.md + README.md) with the
    seeded-conditions contract documented in README.md: batch >= 2,
    overlap-matrix rejection, and scope violation.
  * unit_055: the captured /create-development-harness output
    artifacts (config.json + phase-graph.json) match the README
    contract AND conform to v2 schemas AND will actually exercise
    the three seeded conditions when the harness is run against
    the fixture.

The fixture itself is consumed ad-hoc (not by CI); these tests are
structural presence + doc-shape + data-shape contracts ensuring
the fixture stays consistent with the PHASE_013 acceptance
criteria and with downstream units 056-058 that will run against
it.
"""
import json
import unittest
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "self-test"
ROADMAP = FIXTURE_DIR / "ROADMAP.md"
README = FIXTURE_DIR / "README.md"
CONFIG = FIXTURE_DIR / "config.json"
PHASE_GRAPH = FIXTURE_DIR / "phase-graph.json"


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


# ---------------------------------------------------------------------
# unit_055 -- captured /create-development-harness artifacts
# ---------------------------------------------------------------------


class TestFixtureConfigJson(unittest.TestCase):
    """The fixture's config.json is what unit_055 would have produced
    if /create-development-harness had run interactively against the
    ROADMAP. It is committed to the repo so downstream units 056-058
    can operate against a stable starting point.

    The harness invoke flow (commands/invoke.md Step 4) reads
    execution_mode.parallelism to decide dispatch mode, and unit_053's
    schema precheck reads schema_version. Every v2-required field must
    be present and shaped correctly."""

    def _load(self):
        self.assertTrue(CONFIG.is_file(), f"fixture config.json missing at {CONFIG}")
        return json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_schema_version_is_v2(self):
        cfg = self._load()
        self.assertEqual(
            cfg["schema_version"], "2.0",
            "fixture config must be v2 so validate_harness.py does not "
            "reject it with the re-create pointer (unit_053 behavior)",
        )

    def test_parallelism_enabled_true(self):
        """PHASE_013 acceptance: 'enable parallelism'. Without this,
        the fixture exercises only the in-tree fast path and none of
        the PHASE_007/009/010 parallel machinery is actually tested."""
        cfg = self._load()
        parallelism = cfg["execution_mode"]["parallelism"]
        self.assertIs(
            parallelism["enabled"], True,
            "fixture parallelism.enabled must be true so the seeded "
            "batch >= 2 condition actually fires",
        )

    def test_parallelism_defaults_preserved(self):
        """The full parallelism block shape (max_concurrent_units,
        conflict_strategy, require_touches_paths, allow_cross_phase)
        must be present so the config is self-documenting per the
        unit_048 /create-development-harness Phase 2 instruction."""
        cfg = self._load()
        parallelism = cfg["execution_mode"]["parallelism"]
        self.assertEqual(parallelism["max_concurrent_units"], 3)
        self.assertEqual(parallelism["conflict_strategy"], "abort_batch")
        self.assertIs(parallelism["require_touches_paths"], True)
        self.assertIs(parallelism["allow_cross_phase"], False)

    def test_not_deploy_affecting(self):
        """Tasklet is a test fixture -- deployment.target must be
        'none' so PHASE completion reviews don't block on a missing
        deploy verifier."""
        cfg = self._load()
        self.assertEqual(cfg["deployment"]["target"], "none")


class TestFixturePhaseGraphJson(unittest.TestCase):
    """The fixture's phase-graph.json must match the ASCII graph
    promised in README.md exactly (unit_id, parallel_safe,
    touches_paths). Without this, the three seeded conditions will
    not fire and PHASE_013 becomes a no-op."""

    def _load(self):
        self.assertTrue(PHASE_GRAPH.is_file(),
                        f"fixture phase-graph.json missing at {PHASE_GRAPH}")
        return json.loads(PHASE_GRAPH.read_text(encoding="utf-8"))

    def _units_by_id(self):
        graph = self._load()
        units = {}
        for phase in graph["phases"]:
            for unit in phase["units"]:
                units[unit["id"]] = unit
        return units

    def test_schema_version_is_v2(self):
        self.assertEqual(self._load()["schema_version"], "2.0")

    def test_has_two_phases_with_expected_ids(self):
        graph = self._load()
        phase_ids = [p["id"] for p in graph["phases"]]
        self.assertEqual(phase_ids, ["PHASE_A", "PHASE_B"])

    def test_all_six_units_present_with_expected_ids(self):
        units = self._units_by_id()
        expected = {"unit_a1", "unit_a2", "unit_a3", "unit_b1", "unit_b2", "unit_b3"}
        self.assertEqual(set(units.keys()), expected)

    def test_every_unit_is_parallel_safe(self):
        """README promises all 6 units parallel_safe=true so the
        batch composition tests actually exercise parallel paths."""
        units = self._units_by_id()
        for uid, unit in units.items():
            self.assertIs(
                unit["parallel_safe"], True,
                f"{uid} must have parallel_safe=true per README contract",
            )

    def test_seeded_overlap_unit_a3_overlaps_unit_a2(self):
        """The overlap-rejection seed: a3 and a2 must both declare
        src/items/routes.py in their touches_paths so compute_parallel_
        batch._unit_pair_overlaps rejects a3 with path_overlap_with:a2."""
        units = self._units_by_id()
        self.assertIn("src/items/routes.py", units["unit_a2"]["touches_paths"])
        self.assertIn("src/items/routes.py", units["unit_a3"]["touches_paths"])

    def test_seeded_scope_violation_unit_b2_omits_seeds_glob(self):
        """The scope-violation seed: unit_b2's description requires
        writing src/seeds/users.json but touches_paths must NOT include
        src/seeds/** -- that's what makes a faithful sub-agent's diff
        trip the scope check."""
        units = self._units_by_id()
        touches = units["unit_b2"]["touches_paths"]
        self.assertIn("src/users/routes.py", touches,
                      "unit_b2 must declare src/users/routes.py (its real work)")
        self.assertIn("src/router.py", touches,
                      "unit_b2 must declare src/router.py (route registration)")
        # The negative claim: no glob in touches_paths covers src/seeds/
        # under fnmatch semantics.
        import fnmatch
        for pattern in touches:
            self.assertFalse(
                fnmatch.fnmatchcase("src/seeds/users.json", pattern),
                f"unit_b2 touches_paths must not cover src/seeds/users.json "
                f"(the scope-violation seed), but pattern {pattern!r} matches",
            )

    def test_seeded_scope_violation_description_names_the_violating_file(self):
        """Without the description telling the sub-agent to write
        src/seeds/users.json, the violation would not actually fire.
        The description must name the violating file explicitly."""
        units = self._units_by_id()
        self.assertIn(
            "src/seeds/users.json",
            units["unit_b2"]["description"],
            "unit_b2 description must name src/seeds/users.json so a "
            "faithful sub-agent actually writes the violating file",
        )

    def test_unit_a3_description_flags_the_overlap_seed(self):
        """Make sure future readers of phase-graph.json immediately
        see that unit_a3's overlap with unit_a2 is intentional."""
        units = self._units_by_id()
        desc_lower = units["unit_a3"]["description"].lower()
        self.assertIn("seeded overlap", desc_lower,
                      "unit_a3 description must flag the overlap as seeded")
        self.assertIn("path_overlap_with:unit_a2",
                      units["unit_a3"]["description"],
                      "unit_a3 description must name the exact exclusion "
                      "reason downstream operators will see")

    def test_unit_b2_description_flags_the_scope_violation_seed(self):
        units = self._units_by_id()
        desc_lower = units["unit_b2"]["description"].lower()
        self.assertIn("seeded scope violation", desc_lower,
                      "unit_b2 description must flag the scope violation as seeded")
        self.assertIn("scope_violation", units["unit_b2"]["description"],
                      "unit_b2 description must name the conflict.category "
                      "operators will see")


if __name__ == "__main__":
    unittest.main()
