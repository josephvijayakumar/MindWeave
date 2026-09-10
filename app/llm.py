from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import defaultdict

import json
import os
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

from .models import ProposalKind, ProposedChange


class LLMProvider(ABC):
    @abstractmethod
    def propose(self, messages, existing_knowledge) -> list[ProposedChange]: ...


class HeuristicProvider(LLMProvider):
    """Offline provider for the MVP; replace with Gemini/Claude adapter in production."""
    SIGNAL = re.compile(r"\?|\b(is|are|means|because|therefore|example|for example|defined|retriev|embedding|model|database)\b", re.I)

    def propose(self, messages, existing_knowledge) -> list[ProposedChange]:
        meaningful = [m for m in messages if self.SIGNAL.search(m["content"]) and len(m["content"].strip()) > 20]
        if not meaningful: return []
        groups = defaultdict(list)
        for message in meaningful:
            words = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", message["content"])
            topic = next((w.upper() for w in words if w.lower() in {"rag", "llm", "api"}), (words[0].title() if words else "General Learning"))
            groups[topic].append(message)
        known = {(row["topic"].lower(), row["concept"].lower()) for row in existing_knowledge}
        proposals = []
        for topic, batch in groups.items():
            source = [m["id"] for m in batch]
            explanation_messages = [m["content"].strip() for m in batch if not m["content"].strip().endswith("?")]
            questions = [m["content"].strip() for m in batch if m["content"].strip().endswith("?")]
            concept = topic
            explanation = " ".join(explanation_messages) or "Discussion raised an unresolved question: " + questions[0]
            kind = ProposalKind.UPDATE if (topic.lower(), concept.lower()) in known else (ProposalKind.QUESTION if not explanation_messages else ProposalKind.CREATE)
            related = [{"concept": w.upper(), "type": "related_to"} for w in ("RAG", "Embeddings", "LLMs", "Vector Databases") if w.lower() != topic.lower() and w.lower() in explanation.lower()]
            proposals.append(ProposedChange(topic=topic, kind=kind, concept=concept, explanation=explanation, reason="Learning-oriented discussion detected in imported messages.", source_message_ids=source, confidence=0.72 if explanation_messages else 0.58, related_concepts=related))
        return proposals


class GeminiProvider(LLMProvider):
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set")
        if not genai:
            raise RuntimeError("google-genai is not installed")
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

    def propose(self, messages, existing_knowledge) -> list[ProposedChange]:
        if not messages:
            return []

        system_instruction = (
            "You are an assistant that analyzes learning-group discussions and creates structured knowledge proposals. "
            "You must return a JSON list of objects. Each object must have: topic, kind (CREATE, UPDATE, CONTRADICTION, QUESTION), "
            "concept, explanation, reason, source_message_ids (list of integers matching provided IDs), confidence (0-1), related_concepts (list of objects with 'concept' and 'type' string fields. e.g. type='depends_on', 'contrasts_with', 'related_to')."
        )

        prompt = "Messages to analyze:\\n"
        for m in messages:
            prompt += f"[{m['id']}] {m['sender']}: {m['content']}\\n"

        prompt += "\\nExisting knowledge summary:\\n"
        for k in existing_knowledge:
            prompt += f"- {k['topic']} -> {k['concept']}: {k['explanation']}\\n"

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
            )
        )

        if not response.text:
            return []

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        allowed_ids = {m["id"] for m in messages}
        valid_kinds = {k.value for k in ProposalKind}
        proposals = []

        for item in data:
            try:
                kind_str = item.get("kind")
                if kind_str not in valid_kinds:
                    continue

                source_ids = item.get("source_message_ids", [])
                if not isinstance(source_ids, list) or not all(sid in allowed_ids for sid in source_ids):
                    continue

                confidence = item.get("confidence", 0.0)
                if not (0.0 <= confidence <= 1.0):
                    continue

                if not source_ids:
                    continue

                proposals.append(ProposedChange(
                    topic=str(item.get("topic", "")),
                    kind=ProposalKind(kind_str),
                    concept=str(item.get("concept", "")),
                    explanation=str(item.get("explanation", "")),
                    reason=str(item.get("reason", "")),
                    source_message_ids=source_ids,
                    confidence=float(confidence),
                    related_concepts=item.get("related_concepts", [])
                ))
            except (ValueError, TypeError):
                continue

        return proposals
