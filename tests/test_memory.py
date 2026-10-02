"""Offline tests for JARVIS persistent local memory."""

import tempfile
import sqlite3
import unittest
from pathlib import Path

from memory import MemoryStore, MemoryStoreError, parse_memory_intent, parse_memory_request


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test_jarvis_memory.db"
        self.store = MemoryStore(str(self.database_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def insert_legacy_memories(self, *contents: str) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.executemany(
                "INSERT INTO memories (content) VALUES (?)",
                [(content,) for content in contents],
            )

    def test_parse_memory_request_strips_remember_prefix(self):
        self.assertEqual(
            parse_memory_request("Remember that my name is Harshit."),
            "my name is Harshit.",
        )

    def test_parse_memory_intent_handles_natural_language(self):
        self.assertEqual(
            parse_memory_intent("Keep in mind that I am learning Python."),
            {"action": "save", "content": "I am learning Python"},
        )
        self.assertEqual(
            parse_memory_intent("What do you know about me?"),
            {"action": "retrieve", "query": "me"},
        )
        self.assertEqual(
            parse_memory_intent("Do you remember anything about Python?"),
            {"action": "retrieve", "query": "python"},
        )
        self.assertEqual(
            parse_memory_intent("Forget the last thing you remembered."),
            {"action": "delete", "target": "latest"},
        )
        self.assertIsNone(parse_memory_intent("Remember that"))

    def test_add_memory_and_list_memories(self):
        self.store.add_memory("my name is Harshit")
        self.store.add_memory("I like tea")

        memories = self.store.list_memories()
        self.assertEqual(memories, ["my name is Harshit", "I like tea"])

    def test_adding_duplicate_memory_does_not_create_duplicate_entry(self):
        self.store.add_memory("I like mint tea.")
        self.store.add_memory("I like mint tea")

        self.assertEqual(self.store.list_memories(), ["I like mint tea"])

    def test_cleanup_duplicate_rows_preserves_newest_record(self):
        self.insert_legacy_memories("same memory", "distinct memory", "same memory")

        removed = self.store.cleanup_duplicate_memories()

        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT id, content FROM memories ORDER BY id"
            ).fetchall()
        self.assertEqual(removed, 1)
        self.assertEqual(rows, [(2, "distinct memory"), (3, "same memory")])

    def test_cleanup_preserves_distinct_similar_memories(self):
        memories = ("I like tea", "I like green tea", "I like coffee")
        self.insert_legacy_memories(*memories)

        removed = self.store.cleanup_duplicate_memories()

        self.assertEqual(removed, 0)
        self.assertEqual(self.store.list_memories(), list(memories))

    def test_cleanup_empty_store(self):
        self.assertEqual(self.store.cleanup_duplicate_memories(), 0)
        self.assertEqual(self.store.list_memories(), [])

    def test_cleanup_already_clean_store(self):
        self.store.add_memory("first memory")
        self.store.add_memory("second memory")

        self.assertEqual(self.store.cleanup_duplicate_memories(), 0)
        self.assertEqual(self.store.list_memories(), ["first memory", "second memory"])

    def test_cleanup_is_idempotent(self):
        self.insert_legacy_memories("duplicate", "duplicate")

        self.assertEqual(self.store.cleanup_duplicate_memories(), 1)
        after_first_cleanup = self.store.list_memories()
        self.assertEqual(self.store.cleanup_duplicate_memories(), 0)
        self.assertEqual(self.store.list_memories(), after_first_cleanup)

    def test_cleanup_persists_after_reopening_store(self):
        self.insert_legacy_memories("persisted duplicate", "persisted duplicate")
        self.store.cleanup_duplicate_memories()

        reopened = MemoryStore(str(self.database_path))

        self.assertEqual(reopened.list_memories(), ["persisted duplicate"])

    def test_get_relevant_memories_filters_by_query_terms(self):
        self.store.add_memory("my name is Harshit")
        self.store.add_memory("I prefer coffee")

        relevant = self.store.get_relevant_memories("Harshit")
        self.assertEqual(relevant, ["my name is Harshit"])

    def test_get_relevant_memories_accepts_me_and_my_variants(self):
        self.store.add_memory("favorite language is Python")
        self.store.add_memory("I prefer tea")

        intent = parse_memory_intent("What do you know about me?")
        assert intent is not None
        relevant = self.store.get_relevant_memories(intent["query"])
        self.assertEqual(relevant, ["favorite language is Python", "I prefer tea"])

    def test_profile_retrieval_returns_five_most_recent_memories_by_default(self):
        for index in range(7):
            self.store.add_memory(f"profile memory {index}")

        self.assertEqual(
            self.store.get_relevant_memories("me"),
            [f"profile memory {index}" for index in range(2, 7)],
        )

    def test_get_relevant_memories_normalizes_case_punctuation_and_whitespace(self):
        self.store.add_memory("My favorite color is blue")
        self.store.add_memory("My favorite language is Python")

        relevant = self.store.get_relevant_memories("  FAVORITE-color!!!  ")

        self.assertEqual(relevant, ["My favorite color is blue"])

    def test_get_relevant_memories_requires_all_meaningful_query_terms(self):
        self.store.add_memory("My favorite language is Python")
        self.store.add_memory("I like coffee")

        language_match = self.store.get_relevant_memories("What is my favorite language?")
        color_match = self.store.get_relevant_memories("What is my favorite color?")

        self.assertEqual(language_match, ["My favorite language is Python"])
        self.assertEqual(color_match, [])

    def test_get_relevant_memories_does_not_match_substrings(self):
        self.store.add_memory("I like coffee")

        self.assertEqual(self.store.get_relevant_memories("C++"), [])

    def test_get_relevant_memories_rejects_ambiguous_reference(self):
        self.store.add_memory("I like tea")

        self.assertEqual(self.store.get_relevant_memories("it"), [])

    def test_get_relevant_memories_does_not_infer_synonyms(self):
        self.store.add_memory("I like mint tea")

        self.assertEqual(self.store.get_relevant_memories("favorite beverage"), [])

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
