"""Tests for compile_roadmap.py via subprocess."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
COMPILE_SCRIPT = SCRIPT_DIR / "compile_roadmap.py"


def run_compile_roadmap(roadmap_path):
    """Run compile_roadmap.py with --roadmap and return parsed JSON from stdout."""
    result = subprocess.run(
        [sys.executable, str(COMPILE_SCRIPT), "--roadmap", str(roadmap_path)],
        capture_output=True,
        text=True,
        cwd=str(SCRIPT_DIR),
    )
    result.check_returncode()
    return json.loads(result.stdout)


class TestCompileRoadmap(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))

        # roadmap_h2.md: 3 H2 headings
        roadmap_h2 = Path(self.temp_dir) / "roadmap_h2.md"
        roadmap_h2.write_text(
            "## Auth System\n\n## News Scraper\n\n## Dashboard UI\n",
            encoding="utf-8",
        )
        self.roadmap_h2 = roadmap_h2

        # roadmap_h1.md: H1 headings only
        roadmap_h1 = Path(self.temp_dir) / "roadmap_h1.md"
        roadmap_h1.write_text("# Auth\n\n# Scraper\n", encoding="utf-8")
        self.roadmap_h1 = roadmap_h1

        # roadmap_empty.md: empty file
        roadmap_empty = Path(self.temp_dir) / "roadmap_empty.md"
        roadmap_empty.write_text("", encoding="utf-8")
        self.roadmap_empty = roadmap_empty

        # roadmap_no_headings.md: paragraph text only
        roadmap_no_headings = Path(self.temp_dir) / "roadmap_no_headings.md"
        roadmap_no_headings.write_text(
            "Some paragraph text here.\nNo markdown headings.\n",
            encoding="utf-8",
        )
        self.roadmap_no_headings = roadmap_no_headings

        # roadmap_slug.md: for slug generation (special chars, spaces, case)
        roadmap_slug = Path(self.temp_dir) / "roadmap_slug.md"
        roadmap_slug.write_text("## Auth & OAuth! (v2)\n", encoding="utf-8")
        self.roadmap_slug = roadmap_slug

    def test_h2_headings_produce_phases(self):
        output = run_compile_roadmap(self.roadmap_h2)
        phases = output["phases"]
        self.assertEqual(len(phases), 3)
        slugs = [p["slug"] for p in phases]
        self.assertEqual(slugs, ["auth-system", "news-scraper", "dashboard-ui"])

    def test_h1_fallback(self):
        output = run_compile_roadmap(self.roadmap_h1)
        phases = output["phases"]
        self.assertEqual(len(phases), 2)
        slugs = [p["slug"] for p in phases]
        self.assertEqual(slugs, ["auth", "scraper"])

    def test_empty_roadmap(self):
        output = run_compile_roadmap(self.roadmap_empty)
        phases = output["phases"]
        self.assertEqual(len(phases), 1)
        self.assertEqual(phases[0]["slug"], "roadmap_empty")

    def test_no_headings_single_phase(self):
        output = run_compile_roadmap(self.roadmap_no_headings)
        phases = output["phases"]
        self.assertEqual(len(phases), 1)
        self.assertEqual(phases[0]["slug"], "roadmap_no_headings")

    def test_slug_generation(self):
        output = run_compile_roadmap(self.roadmap_slug)
        phases = output["phases"]
        self.assertEqual(len(phases), 1)
        slug = phases[0]["slug"]
        self.assertEqual(slug, "auth-oauth-v2")
        self.assertNotIn("&", slug)
        self.assertNotIn("!", slug)
        self.assertNotIn("(", slug)
        self.assertNotIn(")", slug)
        self.assertTrue(slug.islower())
        self.assertIn("-", slug)


if __name__ == "__main__":
    unittest.main()
