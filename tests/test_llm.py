import os
import json
import unittest
from unittest.mock import patch, MagicMock
from app.llm import GeminiProvider
from app.models import ProposalKind

class GeminiProviderTests(unittest.TestCase):
    def setUp(self):
        os.environ["GEMINI_API_KEY"] = "fake-key"

    @patch("app.llm.genai.Client")
    def test_propose_valid_output(self, mock_client):
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {
                "topic": "Python",
                "kind": "CREATE",
                "concept": "Decorators",
                "explanation": "A way to wrap functions.",
                "reason": "Useful for logging.",
                "source_message_ids": [1, 2],
                "confidence": 0.9,
                "related_concepts": [{"concept": "Functions", "type": "depends_on"}]
            }
        ])
        mock_client.return_value.models.generate_content.return_value = mock_response
        provider = GeminiProvider()

        messages = [
            {"id": 1, "content": "What is a decorator?", "sender": "Alice", "sent_at": "2024-01-01T10:00:00", "is_system": False, "external_id": "ext1", "analyzed_at": None},
            {"id": 2, "content": "It wraps a function.", "sender": "Bob", "sent_at": "2024-01-01T10:01:00", "is_system": False, "external_id": "ext2", "analyzed_at": None}
        ]
        
        proposals = provider.propose(messages, [])
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].topic, "Python")
        self.assertEqual(proposals[0].source_message_ids, [1, 2])
        self.assertEqual(proposals[0].kind, ProposalKind.CREATE)

    @patch("app.llm.genai.Client")
    def test_propose_invalid_kind(self, mock_client):
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {
                "topic": "Python",
                "kind": "INVALID_KIND",
                "concept": "Decorators",
                "explanation": "A way to wrap functions.",
                "reason": "Useful for logging.",
                "source_message_ids": [1],
                "confidence": 0.9,
                "related_concepts": []
            }
        ])
        mock_client.return_value.models.generate_content.return_value = mock_response
        provider = GeminiProvider()

        messages = [{"id": 1, "content": "hello", "sender": "Alice", "sent_at": "2024-01-01", "is_system": False, "external_id": "e", "analyzed_at": None}]
        proposals = provider.propose(messages, [])
        self.assertEqual(len(proposals), 0)

    @patch("app.llm.genai.Client")
    def test_propose_invalid_source_ids(self, mock_client):
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {
                "topic": "Python",
                "kind": "CREATE",
                "concept": "Decorators",
                "explanation": "A way to wrap functions.",
                "reason": "Useful for logging.",
                "source_message_ids": [999], # Not in messages
                "confidence": 0.9,
                "related_concepts": []
            }
        ])
        mock_client.return_value.models.generate_content.return_value = mock_response
        provider = GeminiProvider()

        messages = [{"id": 1, "content": "hello", "sender": "Alice", "sent_at": "2024-01-01", "is_system": False, "external_id": "e", "analyzed_at": None}]
        proposals = provider.propose(messages, [])
        self.assertEqual(len(proposals), 0)

    @patch("app.llm.genai.Client")
    def test_propose_provider_failure(self, mock_client):
        mock_client.return_value.models.generate_content.side_effect = Exception("API Error")
        provider = GeminiProvider()
        messages = [{"id": 1, "content": "hello", "sender": "Alice", "sent_at": "2024-01-01", "is_system": False, "external_id": "e", "analyzed_at": None}]
        
        with self.assertRaises(Exception):
            provider.propose(messages, [])
