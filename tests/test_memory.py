"""Offline tests for JARVIS persistent local memory."""

import os
import tempfile
import unittest
from pathlib import Path

from memory import MemoryStore, MemoryStoreError, parse_memory_request


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test_jarvis_memory.db"
        self.store = MemoryStore(str(self.database_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_memory_request_strips_remember_prefix(self):
        self.assertEqual(
            parse_memory_request("Remember that my name is Harshit."),
            "my name is Harshit.",
        )

    def test_add_memory_and_list_memories(self):
        self.store.add_memory("my name is Harshit")
        self.store.add_memory("I like tea")

        memories = self.store.list_memories()
        self.assertEqual(memories, ["my name is Harshit", "I like tea"])

    def test_get_relevant_memories_filters_by_query_terms(self):
        self.store.add_memory("my name is Harshit")
        self.store.add_memory("I prefer coffee")

        relevant = self.store.get_relevant_memories("Harshit")
        self.assertEqual(relevant, ["my name is Harshit"])

    def test_delete_memory_removes_specific_memory(self):
        self.store.add_memory("my name is Harshit")
        self.store.add_memory("I like tea")

        deleted = self.store.delete_memory("my name is Harshit")
        self.assertTrue(deleted)
        self.assertEqual(self.store.list_memories(), ["I like tea"])

    def test_clear_memories_removes_all_saved_entries(self):
        self.store.add_memory("my name is Harshit")
        self.store.add_memory("I like tea")

        count = self.store.clear_memories()
        self.assertEqual(count, 2)
        self.assertEqual(self.store.list_memories(), [])

    def test_adding_blank_memory_raises_error(self):
        with self.assertRaises(MemoryStoreError):
            self.store.add_memory("   ")

    def test_persistence_survives_new_store_instance(self):
        self.store.add_memory("my favorite color is blue")

        reopened = MemoryStore(str(self.database_path))
        self.assertEqual(reopened.list_memories(), ["my favorite color is blue"])


if __name__ == "__main__":
    unittest.main()
