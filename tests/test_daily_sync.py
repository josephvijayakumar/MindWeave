import unittest
import tempfile
import os
from pathlib import Path

from backend.db import Database
from backend.cli import build_parser, _get_llm_provider
from backend.models import ParsedMessage


class DailySyncTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_daily.db"
        self.test_db = Database(str(self.db_path))
        self.test_db.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_parser_daily_sync_args(self):
        parser = build_parser()
        args = parser.parse_args(["daily-sync", "--group", "Test Group", "--limit", "100", "--dry-run", "--discover-links"])
        self.assertEqual(args.command, "daily-sync")
        self.assertEqual(args.group, "Test Group")
        self.assertEqual(args.limit, 100)
        self.assertTrue(args.dry_run)
        self.assertTrue(args.discover_links)

    def test_cli_parser_setup_schedule_args(self):
        parser = build_parser()
        args = parser.parse_args(["setup-schedule", "--install", "--time", "03:30"])
        self.assertEqual(args.command, "setup-schedule")
        self.assertTrue(args.install)
        self.assertEqual(args.time, "03:30")

    def test_llm_provider_env_selection(self):
        # Default should return provider without raising
        os.environ["LLM_PROVIDER"] = "heuristic"
        provider = _get_llm_provider()
        self.assertEqual(provider.__class__.__name__, "HeuristicProvider")


if __name__ == "__main__":
    unittest.main()
