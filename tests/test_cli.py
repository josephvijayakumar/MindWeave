import tempfile
import unittest
from pathlib import Path

from app.cli import main


class CliTests(unittest.TestCase):
    def test_cli_import_analyze_and_export_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "test.db"
            chat = root / "chat.txt"
            review = root / "review.md"
            chat.write_text("10/09/2026, 6:59:11 PM - Priya: RAG retrieves relevant context before an answer is generated.", encoding="utf-8")
            self.assertEqual(main(["--db", str(database), "import", str(chat)]), 0)
            self.assertEqual(main(["--db", str(database), "analyze"]), 0)
            self.assertEqual(main(["--db", str(database), "export-review", "--output", str(review)]), 0)
            self.assertIn("MindWeave review", review.read_text(encoding="utf-8"))

    def test_bulk_approval_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(main(["--db", str(Path(directory) / "test.db"), "approve-all"]), 1)
