import unittest
from app.parser import parse_whatsapp_export


class WhatsappParserTests(unittest.TestCase):
    def test_parses_multiline_android_message(self):
        messages = parse_whatsapp_export("12/09/2026, 09:10 - Priya: First line\nSecond line\n12/09/2026, 09:11 - Arun: Next")
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].sender, "Priya")
        self.assertEqual(messages[0].content, "First line\nSecond line")

    def test_marks_system_message(self):
        messages = parse_whatsapp_export("12/09/2026, 09:10 - Priya joined using this group's invite link")
        self.assertTrue(messages[0].is_system)

    def test_parses_recent_android_timestamp_with_seconds_and_am_pm(self):
        messages = parse_whatsapp_export("10/09/2026, 6:59:11 PM - Priya: Here is a learning message")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].sender, "Priya")
        self.assertEqual(messages[0].content, "Here is a learning message")

    def test_parses_bracketed_ios_timestamp(self):
        messages = parse_whatsapp_export("[10/09/2026, 18:59:11] Priya: A bracketed message")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].sender, "Priya")


if __name__ == "__main__": unittest.main()
