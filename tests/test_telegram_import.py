import unittest
import json
from datetime import datetime

from app.parser import parse_telegram_json


class TelegramParserTests(unittest.TestCase):
    def test_parses_telegram_json(self):
        content = {
            "name": "Learning Group",
            "type": "public_group",
            "id": 12345,
            "messages": [
                {
                    "id": 100,
                    "type": "message",
                    "date": "2026-09-12T09:10:22",
                    "from": "Priya",
                    "text": "RAG is great!"
                },
                {
                    "id": 101,
                    "type": "message",
                    "date": "2026-09-12T09:11:00",
                    "from": "Sam",
                    "text": ["I agree, and ", {"type": "link", "text": "here is a link"}]
                }
            ]
        }
        
        parsed = parse_telegram_json(json.dumps(content))
        self.assertEqual(len(parsed), 2)
        
        self.assertEqual(parsed[0].sender, "Priya")
        self.assertEqual(parsed[0].content, "RAG is great!")
        self.assertEqual(parsed[0].sent_at, datetime(2026, 9, 12, 9, 10, 22))
        
        self.assertEqual(parsed[1].sender, "Sam")
        self.assertEqual(parsed[1].content, "I agree, and here is a link")
