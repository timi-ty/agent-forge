"""Tests for normalize_issues.py via subprocess."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent dir so we can import from scripts if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SCRIPT_DIR = Path(__file__).resolve().parent.parent
NORMALIZE_SCRIPT = SCRIPT_DIR / "normalize_issues.py"


def run_normalize_issues(text=None, input_path=None, output_dir=None, start_id=None):
    """Run normalize_issues.py and return (returncode, parsed JSON from stdout)."""
    cmd = [sys.executable, str(NORMALIZE_SCRIPT)]
    if text is not None:
        cmd.extend(["--text", text])
    if input_path is not None:
        cmd.extend(["--input", str(input_path)])
    if output_dir is not None:
        cmd.extend(["--output-dir", str(output_dir)])
    if start_id is not None:
        cmd.extend(["--start-id", str(start_id)])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(SCRIPT_DIR),
    )
    try:
        output = json.loads(result.stdout) if result.stdout else []
    except json.JSONDecodeError:
        output = []
    return result.returncode, output


class TestNormalizeIssues(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))

    def test_numbered_list_splitting(self):
        text = "1. Login fails\n2. Slow loading\n3. Missing button"
        output_dir = self.temp_dir / "issues"
        returncode, issues = run_normalize_issues(text=text, output_dir=str(output_dir))
        self.assertEqual(returncode, 0)
        self.assertEqual(len(issues), 3, f"Expected 3 issues, got: {issues}")

    def test_bullet_splitting(self):
        text = "- Login fails\n- Slow loading"
        output_dir = self.temp_dir / "issues"
        returncode, issues = run_normalize_issues(text=text, output_dir=str(output_dir))
        self.assertEqual(returncode, 0)
        self.assertEqual(len(issues), 2, f"Expected 2 issues, got: {issues}")

    def test_single_issue(self):
        text = "Login page crashes on submit"
        output_dir = self.temp_dir / "issues"
        returncode, issues = run_normalize_issues(text=text, output_dir=str(output_dir))
        self.assertEqual(returncode, 0)
        self.assertEqual(len(issues), 1, f"Expected 1 issue, got: {issues}")

    def test_output_has_required_fields(self):
        text = "Login page crashes on submit"
        output_dir = self.temp_dir / "issues"
        returncode, issues = run_normalize_issues(text=text, output_dir=str(output_dir))
        self.assertEqual(returncode, 0)
        self.assertEqual(len(issues), 1)
        issue = issues[0]
        for key in ("schema_version", "id", "title", "severity", "status"):
            self.assertIn(key, issue, f"Issue must have required field: {key}")

    def test_writes_to_output_dir(self):
        output_dir = self.temp_dir / "issues_out"
        text = "Login page crashes on submit"
        returncode, issues = run_normalize_issues(text=text, output_dir=str(output_dir))
        self.assertEqual(returncode, 0)
        issue_file = output_dir / "ISSUE_001.json"
        self.assertTrue(issue_file.exists(), f"Expected ISSUE_001.json in {output_dir}")
        with open(issue_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("id", data)
        self.assertEqual(data["id"], "ISSUE_001")


if __name__ == "__main__":
    unittest.main()
