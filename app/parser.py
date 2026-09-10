from __future__ import annotations

import hashlib
import re
from datetime import datetime

from .models import ParsedMessage

# Android: 12/09/2026, 09:10:22 pm - Priya: hello
# iOS: [12/09/2026, 09:10:22] Priya: hello
# WhatsApp changes this presentation by platform, locale and app version.
MESSAGE_START = re.compile(
    r"^(?:\[)?(?P<date>(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})|(?:\d{4}[/-]\d{1,2}[/-]\d{1,2}))"
    r",\s*(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp]\.?\s*[Mm]\.?)?)(?:\])?\s*(?:-\s*)?(?P<body>.*)$"
)


def _timestamp(date: str, time: str) -> datetime | None:
    value = f"{date} {time}".upper().replace(".", "")
    for fmt in (
        "%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%d-%m-%Y %H:%M", "%d-%m-%y %H:%M",
        "%d/%m/%Y %H:%M:%S", "%d/%m/%y %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%d-%m-%y %H:%M:%S",
        "%d/%m/%Y %I:%M %p", "%d/%m/%y %I:%M %p", "%d-%m-%Y %I:%M %p", "%d-%m-%y %I:%M %p",
        "%d/%m/%Y %I:%M:%S %p", "%d/%m/%y %I:%M:%S %p", "%d-%m-%Y %I:%M:%S %p", "%d-%m-%y %I:%M:%S %p",
        "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def parse_whatsapp_export(text: str) -> list[ParsedMessage]:
    """Parse common WhatsApp text exports while preserving multiline messages."""
    records: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw in text.replace("\ufeff", "").replace("\u200e", "").replace("\u200f", "").splitlines():
        match = MESSAGE_START.match(raw)
        if match:
            if current:
                records.append(current)
            body = match.group("body")
            sender, separator, content = body.partition(": ")
            current = {
                "sent_at": _timestamp(match.group("date"), match.group("time")),
                "sender": sender if separator else "System",
                "content": content if separator else body,
                "is_system": not bool(separator),
            }
        elif current:
            current["content"] = f"{current['content']}\n{raw}"
    if current:
        records.append(current)

    parsed = []
    for index, item in enumerate(records):
        fingerprint = f"{index}|{item['sent_at']}|{item['sender']}|{item['content']}"
        parsed.append(ParsedMessage(
            external_id=hashlib.sha256(fingerprint.encode()).hexdigest()[:24],
            sent_at=item["sent_at"], sender=str(item["sender"]), content=str(item["content"]), is_system=bool(item["is_system"])
        ))
    return parsed
