import unittest
import tempfile
import os
from pathlib import Path
from fastapi.testclient import TestClient

from backend.db import Database
from backend.main import app, db
from backend.models import ProposedChange, ProposalKind


class RelationshipTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_mindweave.db"
        self.test_db = Database(str(self.db_path))
        self.test_db.initialize()

        # Seed two sample knowledge items
        with self.test_db.connection() as conn:
            conn.execute(
                "INSERT INTO knowledge_items(topic, concept, explanation, confidence, contributors) VALUES (?, ?, ?, ?, ?)",
                ("AI", "LLMs", "Large language models that generate text based on training data.", 0.95, "[]")
            )
            conn.execute(
                "INSERT INTO knowledge_items(topic, concept, explanation, confidence, contributors) VALUES (?, ?, ?, ?, ?)",
                ("AI", "LLMs as Autocomplete", "Viewing LLMs as advanced autocomplete systems that predict next tokens.", 0.90, "[]")
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_and_delete_relationship(self):
        items = self.test_db.all_knowledge()
        id1, id2 = items[0]["id"], items[1]["id"]

        # Add relationship
        added = self.test_db.add_relationship(id2, id1, "specialization_of")
        self.assertTrue(added)

        # Duplicate should be ignored
        dup = self.test_db.add_relationship(id2, id1, "specialization_of")
        self.assertFalse(dup)

        # Disallow self-linking
        self_rel = self.test_db.add_relationship(id1, id1, "related_to")
        self.assertFalse(self_rel)

        # Verify in relationships list
        rels = self.test_db.relationships()
        self.assertEqual(len(rels), 1)
        rel_id = rels[0]["id"]
        self.assertEqual(rels[0]["relation_type"], "specialization_of")

        # Delete relationship
        deleted = self.test_db.delete_relationship(rel_id)
        self.assertTrue(deleted)
        self.assertEqual(len(self.test_db.relationships()), 0)

    def test_infer_relationships(self):
        # In setUp, 'LLMs as Autocomplete' mentions 'LLMs' in its explanation and title
        discovered = self.test_db.infer_relationships()
        self.assertGreaterEqual(len(discovered), 1)
        
        # Verify it created entries in relationships table
        rels = self.test_db.relationships()
        self.assertGreaterEqual(len(rels), 1)

    def test_graph_and_relationship_routes(self):
        client = TestClient(app)

        # Graph route
        res = client.get("/graph")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Knowledge Graph Visualizer", res.text)
        self.assertIn("mynetwork", res.text)

        # Knowledge route
        k_res = client.get("/knowledge")
        self.assertEqual(k_res.status_code, 200)
        self.assertIn("Knowledge Base", k_res.text)


if __name__ == "__main__":
    unittest.main()
