"""Tests for harness_utils module."""
import sys
import unittest
from pathlib import Path

# Add parent dir so we can import harness_utils
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness_utils import (
    SCHEMA_VERSION,
    check_schema_version,
    insert_managed_block,
    remove_managed_block,
    validate_required_keys,
)


class TestSchemaVersionConstant(unittest.TestCase):
    def test_schema_version_is_v2(self):
        self.assertEqual(SCHEMA_VERSION, "2.0")


class TestCheckSchemaVersion(unittest.TestCase):
    def test_check_schema_version_valid(self):
        data = {"schema_version": SCHEMA_VERSION}
        result = check_schema_version(data)
        self.assertTrue(result["valid"])
        self.assertIsNone(result["error"])

    def test_check_schema_version_missing(self):
        data = {}
        result = check_schema_version(data)
        self.assertFalse(result["valid"])
        self.assertIn("missing schema_version", result["error"])
        self.assertIn("/create-development-harness", result["error"])

    def test_check_schema_version_wrong(self):
        data = {"schema_version": "1.0"}
        result = check_schema_version(data)
        self.assertFalse(result["valid"])
        self.assertIn("expected", result["error"])
        self.assertIn("'2.0'", result["error"])
        self.assertIn("'1.0'", result["error"])

    def test_check_schema_version_v1_rejected_with_recreate_pointer(self):
        """A v1 harness must be rejected with an actionable re-create message."""
        data = {"schema_version": "1.0"}
        result = check_schema_version(data, filepath=".harness/state.json")
        self.assertFalse(result["valid"])
        self.assertIn(".harness/state.json", result["error"])
        self.assertIn("/create-development-harness", result["error"])


class TestValidateRequiredKeys(unittest.TestCase):
    def test_validate_required_keys_all_present(self):
        data = {"a": 1, "b": 2, "c": 3}
        result = validate_required_keys(data, ["a", "b", "c"])
        self.assertTrue(result["valid"])
        self.assertIsNone(result["error"])

    def test_validate_required_keys_missing(self):
        data = {"a": 1, "c": 3}
        result = validate_required_keys(data, ["a", "b", "c"])
        self.assertFalse(result["valid"])
        self.assertIn("missing required keys", result["error"])
        self.assertIn("b", result["error"])


class TestInsertManagedBlock(unittest.TestCase):
    def test_insert_managed_block_into_empty(self):
        content = ""
        block_text = "some block content"
        result = insert_managed_block(content, block_text)
        self.assertIn("<!-- HARNESS:START -->", result)
        self.assertIn("<!-- HARNESS:END -->", result)
        self.assertIn("some block content", result)

    def test_insert_managed_block_into_existing_content(self):
        content = "existing content here"
        block_text = "new block"
        result = insert_managed_block(content, block_text)
        self.assertTrue(result.startswith("existing content here"))
        self.assertIn("<!-- HARNESS:START -->", result)
        self.assertIn("new block", result)
        self.assertIn("<!-- HARNESS:END -->", result)

    def test_insert_managed_block_replaces_existing(self):
        content = "before\n<!-- HARNESS:START -->\nold block\n<!-- HARNESS:END -->\nafter"
        block_text = "new block"
        result = insert_managed_block(content, block_text)
        self.assertIn("before", result)
        self.assertIn("after", result)
        self.assertIn("new block", result)
        self.assertNotIn("old block", result)


class TestRemoveManagedBlock(unittest.TestCase):
    def test_remove_managed_block_present(self):
        content = "before\n<!-- HARNESS:START -->\nblock\n<!-- HARNESS:END -->\nafter"
        new_content, found = remove_managed_block(content)
        self.assertTrue(found)
        self.assertNotIn("<!-- HARNESS:START -->", new_content)
        self.assertNotIn("<!-- HARNESS:END -->", new_content)
        self.assertNotIn("block", new_content)
        self.assertIn("before", new_content)
        self.assertIn("after", new_content)

    def test_remove_managed_block_absent(self):
        content = "just some text without markers"
        new_content, found = remove_managed_block(content)
        self.assertFalse(found)
        self.assertEqual(new_content, content)

    def test_insert_then_remove_roundtrip(self):
        original = "surrounding content\nline two"
        block_text = "managed block"
        with_block = insert_managed_block(original, block_text)
        after_remove, found = remove_managed_block(with_block)
        self.assertTrue(found)
        self.assertIn("surrounding content", after_remove)
        self.assertIn("line two", after_remove)
        self.assertNotIn("managed block", after_remove)
        self.assertNotIn("<!-- HARNESS:START -->", after_remove)
        self.assertNotIn("<!-- HARNESS:END -->", after_remove)


if __name__ == "__main__":
    unittest.main()
