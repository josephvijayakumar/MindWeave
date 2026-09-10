import unittest
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.main import app, db


class ZipImportTests(unittest.TestCase):
    def setUp(self):
        db.initialize()
        self.client = TestClient(app)

    def test_imports_transcript_from_media_zip(self):
        content = BytesIO()
        with ZipFile(content, "w") as archive:
            archive.writestr("WhatsApp Chat - Learning.txt", "12/09/2026, 09:10 - Priya: RAG retrieves relevant context before generating an answer.")
            archive.writestr("IMG-20260912-WA0001.jpg", b"not a real image")
        response = self.client.post("/imports", files={"chat": ("WhatsApp Chat.zip", content.getvalue(), "application/zip")}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
