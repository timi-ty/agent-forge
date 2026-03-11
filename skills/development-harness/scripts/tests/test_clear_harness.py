"""Tests for clear_harness.py dry-run mode."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
CLEAR_SCRIPT = SCRIPT_DIR / "clear_harness.py"

HARNESS_OWNED = "harness-owned"
MANAGED_BLOCK = "managed-block"
PRODUCT_OWNED = "product-owned"
MANAGED_BLOCK_START = "<!-- HARNESS:START -->"
MANAGED_BLOCK_END = "<!-- HARNESS:END -->"


def run_clear_harness(root):
    """Run clear_harness.py (dry-run) and return (returncode, parsed JSON from stdout)."""
    result = subprocess.run(
        [sys.executable, str(CLEAR_SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        cwd=str(SCRIPT_DIR),
    )
    try:
        output = json.loads(result.stdout) if result.stdout else {}
    except json.JSONDecodeError:
        output = {}
    return result.returncode, output


class TestClearHarness(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))

    def test_dry_run_lists_harness_owned(self):
        harness_dir = self.temp_dir / ".harness"
        harness_dir.mkdir()
        (self.temp_dir / "harness_file.txt").write_text("harness owned content", encoding="utf-8")
        (self.temp_dir / "harness_dir").mkdir()
        (self.temp_dir / "harness_dir" / "nested.txt").write_text("nested", encoding="utf-8")

        manifest = {
            "schema_version": "1.0",
            "entries": [
                {"path": "harness_file.txt", "ownership": HARNESS_OWNED, "type": "file"},
                {"path": "harness_dir", "ownership": HARNESS_OWNED, "type": "directory"},
            ],
        }
        (harness_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

        returncode, report = run_clear_harness(self.temp_dir)
        self.assertEqual(returncode, 0)
        self.assertEqual(report.get("mode"), "dry-run")
        will_delete = report.get("will_delete", [])
        paths = [e["path"] for e in will_delete]
        self.assertIn("harness_file.txt", paths)
        self.assertIn("harness_dir", paths)

    def test_dry_run_preserves_product_owned(self):
        harness_dir = self.temp_dir / ".harness"
        harness_dir.mkdir()
        (self.temp_dir / "product_file.txt").write_text("product owned", encoding="utf-8")

        manifest = {
            "schema_version": "1.0",
            "entries": [
                {"path": "product_file.txt", "ownership": PRODUCT_OWNED},
            ],
        }
        (harness_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

        returncode, report = run_clear_harness(self.temp_dir)
        self.assertEqual(returncode, 0)
        will_preserve = report.get("will_preserve", [])
        paths = [e["path"] for e in will_preserve]
        self.assertIn("product_file.txt", paths)

    def test_missing_manifest_exits_error(self):
        harness_dir = self.temp_dir / ".harness"
        harness_dir.mkdir()
        # No manifest.json

        returncode, _ = run_clear_harness(self.temp_dir)
        self.assertEqual(returncode, 1)

    def test_managed_block_detection(self):
        harness_dir = self.temp_dir / ".harness"
        harness_dir.mkdir()
        readme_path = self.temp_dir / "README.md"
        readme_path.write_text(
            "Project title\n\n"
            f"{MANAGED_BLOCK_START}\n"
            "harness managed content\n"
            f"{MANAGED_BLOCK_END}\n",
            encoding="utf-8",
        )

        manifest = {
            "schema_version": "1.0",
            "entries": [
                {"path": "README.md", "ownership": MANAGED_BLOCK},
            ],
        }
        (harness_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

        returncode, report = run_clear_harness(self.temp_dir)
        self.assertEqual(returncode, 0)
        will_remove_block = report.get("will_remove_block", [])
        paths_with_block = [e["path"] for e in will_remove_block if e.get("block_found")]
        self.assertIn("README.md", paths_with_block)


if __name__ == "__main__":
    unittest.main()
