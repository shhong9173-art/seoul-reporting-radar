"""Prevent concurrent GitHub Actions commits to shared JSON files."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTO = ROOT / ".github/workflows/auto-desk.yml"
SCOOP = ROOT / ".github/workflows/scoop-radar.yml"


class SharedWriterTests(unittest.TestCase):
    def test_workflows_use_same_non_cancelling_concurrency_group(self):
        for path in (AUTO, SCOOP):
            value = path.read_text(encoding="utf-8")
            self.assertRegex(
                value,
                r"concurrency:\s*\n(?:\s*#[^\n]*\n)*\s*group:\s*newsroom-radar-writers\n\s*cancel-in-progress:\s*false",
                path.name,
            )

    def test_shared_json_files_are_written_from_both_workflows(self):
        for path in (AUTO, SCOOP):
            value = path.read_text(encoding="utf-8")
            for key in ("dart_numeric.json", "scoop.json"):
                self.assertIn(key, value)

if __name__ == "__main__":
    unittest.main()
