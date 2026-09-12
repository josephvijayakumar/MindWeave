from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from .models import ParsedMessage, ProposedChange


class Database:
    def __init__(self, path: str = "database/mindweave.db"):
        self.path = Path(path)

    def connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS imports (id INTEGER PRIMARY KEY, filename TEXT NOT NULL, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, metadata TEXT);
            CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL REFERENCES imports(id), external_id TEXT NOT NULL, sent_at TEXT, sender TEXT NOT NULL, content TEXT NOT NULL, is_system INTEGER NOT NULL DEFAULT 0, analyzed_at TEXT, UNIQUE(import_id, external_id));
            CREATE TABLE IF NOT EXISTS knowledge_items (id INTEGER PRIMARY KEY, topic TEXT NOT NULL, concept TEXT NOT NULL, explanation TEXT NOT NULL, confidence REAL NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, contributors TEXT NOT NULL DEFAULT '[]', UNIQUE(topic, concept));
            CREATE TABLE IF NOT EXISTS knowledge_versions (id INTEGER PRIMARY KEY, knowledge_item_id INTEGER NOT NULL REFERENCES knowledge_items(id), version INTEGER NOT NULL, explanation TEXT NOT NULL, proposal_id INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS proposals (id INTEGER PRIMARY KEY, topic TEXT NOT NULL, kind TEXT NOT NULL, concept TEXT NOT NULL, explanation TEXT NOT NULL, reason TEXT NOT NULL, source_message_ids TEXT NOT NULL, confidence REAL NOT NULL, related_concepts TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reviewed_at TEXT, reviewer_note TEXT);
            CREATE TABLE IF NOT EXISTS relationships (id INTEGER PRIMARY KEY, from_knowledge_id INTEGER NOT NULL REFERENCES knowledge_items(id), to_knowledge_id INTEGER NOT NULL REFERENCES knowledge_items(id), relation_type TEXT NOT NULL, source_proposal_id INTEGER REFERENCES proposals(id), UNIQUE(from_knowledge_id, to_knowledge_id, relation_type));
            """)
            try:
                conn.execute("ALTER TABLE imports ADD COLUMN metadata TEXT")
            except sqlite3.OperationalError:
                pass

    def import_messages(self, filename: str, messages: list[ParsedMessage]) -> tuple[int, int]:
        with self.connection() as conn:
            import_id = conn.execute("INSERT INTO imports(filename) VALUES (?)", (filename,)).lastrowid
            added = 0
            for message in messages:
                existing = conn.execute("SELECT id FROM messages WHERE external_id = ?", (message.external_id,)).fetchone()
                if not existing:
                    result = conn.execute("INSERT INTO messages(import_id, external_id, sent_at, sender, content, is_system) VALUES (?, ?, ?, ?, ?, ?)", (import_id, message.external_id, message.sent_at.isoformat() if message.sent_at else None, message.sender, message.content, message.is_system))
                    added += result.rowcount
            metadata = json.dumps({"total_messages_in_file": len(messages), "new_messages_added": added})
            conn.execute("UPDATE imports SET metadata=? WHERE id=?", (metadata, import_id))
        return int(import_id), added

    def unprocessed_messages(self, since: str = None, until: str = None, limit: int = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM messages WHERE analyzed_at IS NULL AND is_system = 0"
        params = []
        if since:
            query += " AND sent_at >= ?"
            params.append(since)
        if until:
            query += " AND sent_at <= ?"
            params.append(until)
        query += " ORDER BY sent_at, id"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        with self.connection() as conn:
            return conn.execute(query, params).fetchall()

    def mark_analyzed(self, ids: list[int]) -> None:
        if not ids: return
        with self.connection() as conn:
            conn.execute(f"UPDATE messages SET analyzed_at = CURRENT_TIMESTAMP WHERE id IN ({','.join('?' * len(ids))})", ids)

    def get_messages(self, ids: list[int]) -> list[sqlite3.Row]:
        if not ids: return []
        with self.connection() as conn:
            return conn.execute(f"SELECT * FROM messages WHERE id IN ({','.join('?' * len(ids))}) ORDER BY sent_at, id", ids).fetchall()

    def add_proposals(self, proposals: list[ProposedChange]) -> int:
        with self.connection() as conn:
            for p in proposals:
                conn.execute("INSERT INTO proposals(topic, kind, concept, explanation, reason, source_message_ids, confidence, related_concepts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (p.topic, p.kind, p.concept, p.explanation, p.reason, json.dumps(p.source_message_ids), p.confidence, json.dumps(p.related_concepts)))
        return len(proposals)

    def pending_proposals(self) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute("SELECT * FROM proposals WHERE status = 'PENDING' ORDER BY created_at DESC, id DESC").fetchall()

    def all_knowledge(self) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute("SELECT * FROM knowledge_items ORDER BY topic, concept").fetchall()

    def relationships(self) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute("SELECT r.*, a.concept AS from_concept, b.concept AS to_concept FROM relationships r JOIN knowledge_items a ON a.id=r.from_knowledge_id JOIN knowledge_items b ON b.id=r.to_knowledge_id").fetchall()

    def review(self, proposal_id: int, approved: bool, note: str = "", override_topic: str = None, override_concept: str = None, override_explanation: str = None) -> None:
        with self.connection() as conn:
            proposal_row = conn.execute("SELECT * FROM proposals WHERE id = ? AND status = 'PENDING'", (proposal_id,)).fetchone()
            if not proposal_row: raise ValueError("Proposal is not pending")
            proposal = dict(proposal_row)
            
            if override_topic: proposal["topic"] = override_topic
            if override_concept: proposal["concept"] = override_concept
            if override_explanation: proposal["explanation"] = override_explanation
            
            status = "APPROVED" if approved else "REJECTED"
            conn.execute("UPDATE proposals SET status=?, reviewed_at=CURRENT_TIMESTAMP, reviewer_note=?, topic=?, concept=?, explanation=? WHERE id=?", (status, note, proposal["topic"], proposal["concept"], proposal["explanation"], proposal_id))
            if not approved: return
            existing = conn.execute("SELECT * FROM knowledge_items WHERE topic=? AND concept=?", (proposal["topic"], proposal["concept"])).fetchone()
            if existing:
                version = existing["version"] + 1
                conn.execute("UPDATE knowledge_items SET explanation=?, confidence=?, version=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (proposal["explanation"], proposal["confidence"], version, existing["id"]))
                knowledge_id = existing["id"]
            else:
                knowledge_id = conn.execute("INSERT INTO knowledge_items(topic, concept, explanation, confidence, contributors) VALUES (?, ?, ?, ?, ?)", (proposal["topic"], proposal["concept"], proposal["explanation"], proposal["confidence"], "[]")).lastrowid
                version = 1
            conn.execute("INSERT INTO knowledge_versions(knowledge_item_id, version, explanation, proposal_id) VALUES (?, ?, ?, ?)", (knowledge_id, version, proposal["explanation"], proposal_id))
            for rel in json.loads(proposal["related_concepts"]):
                target_concept = rel if isinstance(rel, str) else rel.get("concept")
                rel_type = "related_to" if isinstance(rel, str) else rel.get("type", "related_to")
                target = conn.execute("SELECT id FROM knowledge_items WHERE LOWER(concept) = LOWER(?)", (target_concept,)).fetchone()
                if target and target["id"] != knowledge_id:
                    conn.execute("INSERT OR IGNORE INTO relationships(from_knowledge_id, to_knowledge_id, relation_type, source_proposal_id) VALUES (?, ?, ?, ?)", (knowledge_id, target["id"], rel_type, proposal_id))

    def add_relationship(self, from_knowledge_id: int, to_knowledge_id: int, relation_type: str = "related_to", source_proposal_id: int | None = None) -> bool:
        if from_knowledge_id == to_knowledge_id:
            return False
        with self.connection() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO relationships(from_knowledge_id, to_knowledge_id, relation_type, source_proposal_id) VALUES (?, ?, ?, ?)",
                (from_knowledge_id, to_knowledge_id, relation_type.strip(), source_proposal_id)
            )
            return cur.rowcount > 0

    def delete_relationship(self, relationship_id: int) -> bool:
        with self.connection() as conn:
            cur = conn.execute("DELETE FROM relationships WHERE id = ?", (relationship_id,))
            return cur.rowcount > 0

    def infer_relationships(self) -> list[dict]:
        items = [dict(r) for r in self.all_knowledge()]
        existing_rels = {
            (r["from_knowledge_id"], r["to_knowledge_id"])
            for r in self.relationships()
        }
        discovered = []

        for a in items:
            for b in items:
                if a["id"] == b["id"] or (a["id"], b["id"]) in existing_rels:
                    continue
                rel_type = None
                # 1. Mention check: b concept mentioned in a explanation
                b_clean = re.sub(r"\(.*?\)", "", b["concept"]).strip()
                if len(b_clean) >= 3:
                    pattern = r"\b" + re.escape(b_clean) + r"\b"
                    if re.search(pattern, a["explanation"], re.IGNORECASE):
                        rel_type = "mentions" if b["topic"] != a["topic"] else "depends_on"

                # 2. Sub-concept check
                if not rel_type and len(b_clean) >= 4 and b_clean.lower() != a["concept"].lower():
                    if b_clean.lower() in a["concept"].lower():
                        rel_type = "specialization_of"

                # 3. Same topic significant word overlap
                if not rel_type and a["topic"] == b["topic"]:
                    a_words = set(re.findall(r"[a-z]{4,}", a["concept"].lower()))
                    b_words = set(re.findall(r"[a-z]{4,}", b["concept"].lower()))
                    stopwords = {"with", "from", "that", "this", "what", "have", "more"}
                    if (a_words & b_words) - stopwords:
                        rel_type = "related_to"

                if rel_type:
                    added = self.add_relationship(a["id"], b["id"], rel_type)
                    if added:
                        existing_rels.add((a["id"], b["id"]))
                        discovered.append({
                            "from_id": a["id"],
                            "from_concept": a["concept"],
                            "to_id": b["id"],
                            "to_concept": b["concept"],
                            "relation_type": rel_type
                        })
        return discovered
