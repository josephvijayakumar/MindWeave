from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ProposalKind(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    CONTRADICTION = "CONTRADICTION"
    QUESTION = "QUESTION"


class ProposalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ParsedMessage:
    external_id: str
    sent_at: datetime | None
    sender: str
    content: str
    is_system: bool = False


@dataclass(frozen=True)
class ProposedChange:
    topic: str
    kind: ProposalKind
    concept: str
    explanation: str
    reason: str
    source_message_ids: list[int]
    confidence: float
    related_concepts: list[dict[str, str]]

