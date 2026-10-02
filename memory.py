"""Persistent local memory storage for JARVIS."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set


_MEMORY_QUERY_STOP_WORDS = {
    "a", "about", "an", "and", "are", "as", "at", "be", "been", "being",
    "but", "by", "can", "could", "did", "do", "does", "for", "from",
    "had", "has", "have", "how", "i", "in", "is", "it", "me", "might",
    "my", "of", "on", "or", "please", "should", "that", "the", "their",
    "them", "there", "these", "they", "this", "those", "to", "was", "what",
    "when", "where", "which", "who", "why", "will", "with", "would", "you",
    "your", "yours", "anything", "know", "remember", "tell",
}
_PROFILE_QUERY_WORDS = _MEMORY_QUERY_STOP_WORDS | {"me", "my", "i"}


def _memory_search_tokens(text: str) -> Set[str]:
    return set(re.findall(r"[A-Za-z0-9']+", text.casefold()))


class MemoryStoreError(ValueError):
    """Raised when a memory request is empty, invalid, or cannot be processed."""


class MemoryStore:
    """Store short user memories in a local SQLite database."""

    def __init__(self, database_path: Optional[str] = None) -> None:
        self._database_path = (
            Path(database_path) if database_path is not None else Path(__file__).resolve().with_name("jarvis_memory.db")
        )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def add_memory(self, content: str) -> str:
        memory = self._normalize_memory(content)
        if not memory:
            raise MemoryStoreError("Please provide a memory to save.")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (content)
                SELECT ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM memories WHERE content = ?
                )
                """,
                (memory, memory),
            )
        return memory

    def cleanup_duplicate_memories(self) -> int:
        """Remove older rows with identical content, preserving the newest ID."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM memories
                WHERE id NOT IN (
                    SELECT MAX(id) FROM memories GROUP BY content
                )
                """
            )
        return cursor.rowcount

    def list_memories(self) -> List[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT content FROM memories ORDER BY id ASC"
            ).fetchall()
        return [row["content"] for row in rows]

    def get_relevant_memories(self, query: Optional[str] = None, limit: int = 5) -> List[str]:
        memories = self.list_memories()
        if not memories:
            return []
        if not query or not query.strip():
            return memories[-limit:]

        query_tokens = _memory_search_tokens(query)
        if "me" in query_tokens and query_tokens <= _PROFILE_QUERY_WORDS:
            return memories[-limit:]

        query_terms = query_tokens - _MEMORY_QUERY_STOP_WORDS
        if not query_terms:
            return []

        relevant: List[str] = []
        for memory in memories:
            memory_terms = _memory_search_tokens(memory)
            if query_terms.issubset(memory_terms):
                relevant.append(memory)
        if not relevant:
            return []
        return relevant[-limit:]

    def delete_memory(self, content: str) -> bool:
        memory = self._normalize_memory(content)
        if not memory:
            return False
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM memories WHERE content = ? LIMIT 1",
                (memory,),
            )
        return cursor.rowcount > 0

    def delete_latest_memory(self) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM memories WHERE id = (SELECT id FROM memories ORDER BY id DESC LIMIT 1)"
            )
        return cursor.rowcount > 0

    def clear_memories(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM memories")
        return cursor.rowcount

    @staticmethod
    def _normalize_memory(value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.rstrip(".")
        return cleaned.strip()


def parse_memory_request(command: str) -> Optional[str]:
    """Return the user-supplied memory text from a remember command, or None."""
    text = command.strip()
    if not text:
        return None
    lowered = text.casefold()
    if lowered.startswith("remember"):
        remainder = text[len("remember") :].strip()
        if remainder.casefold().startswith("that"):
            remainder = remainder[4:].strip()
        if remainder.casefold().startswith("this"):
            remainder = remainder[4:].strip()
        return remainder.strip()
    return None


def parse_memory_intent(command: str) -> Optional[Dict[str, str]]:
    """Recognize save/retrieve/delete memory intent safely without semantic search."""
    text = command.strip()
    if not text:
        return None
    lowered = text.casefold().rstrip(" .!?")

    save_prefixes = (
        "remember ",
        "remember that ",
        "keep in mind ",
        "keep in mind that ",
        "save this ",
        "save this:",
        "save that ",
        "save that:",
        "save ",
        "save the fact that ",
    )
    for prefix in save_prefixes:
        if lowered.casefold().startswith(prefix):
            remainder = text[len(prefix) :].strip()
            remainder = remainder.lstrip(":")
            remainder = remainder.strip()
            if remainder.casefold().startswith("that "):
                remainder = remainder[5:].strip()
            if remainder.casefold().startswith("this "):
                remainder = remainder[5:].strip()
            if remainder.casefold().startswith("the fact that "):
                remainder = remainder[14:].strip()
            remainder = remainder.rstrip(" .!?")
            if remainder.casefold() in {"that", "this"}:
                return None
            if remainder:
                return {"action": "save", "content": remainder}
            return None

    if lowered.casefold().startswith("what do you know about "):
        return {"action": "retrieve", "query": lowered[len("what do you know about ") :].strip()}
    if lowered.casefold().startswith("what do you remember about "):
        return {"action": "retrieve", "query": lowered[len("what do you remember about ") :].strip()}
    if lowered.casefold().startswith("do you remember anything about "):
        return {"action": "retrieve", "query": lowered[len("do you remember anything about ") :].strip()}
    if lowered.casefold().startswith("tell me what you remember"):
        return {"action": "retrieve", "query": ""}
    if lowered.casefold().startswith("what do you remember"):
        return {"action": "retrieve", "query": ""}
    if lowered.casefold().startswith("what do you know"):
        return {"action": "retrieve", "query": ""}

    delete_prefixes = (
        "forget ",
        "forget that ",
        "remove ",
        "remove that ",
        "delete ",
        "delete that ",
    )
    for prefix in delete_prefixes:
        if lowered.casefold().startswith(prefix):
            remainder = text[len(prefix) :].strip()
            remainder = remainder.rstrip(" .!?")
            if not remainder:
                return {"action": "delete", "target": "latest"}
            if remainder.casefold() in {"memory", "that memory", "this memory", "it"}:
                return {"action": "delete", "target": "latest"}
            if remainder.casefold() == "the last thing you remembered":
                return {"action": "delete", "target": "latest"}
            if remainder.casefold().startswith("that "):
                remainder = remainder[5:].strip()
            if remainder.casefold().startswith("this "):
                remainder = remainder[5:].strip()
            if remainder.casefold() in {"memory", "that memory", "this memory", "it"}:
                return {"action": "delete", "target": "latest"}
            if remainder:
                return {"action": "delete", "content": remainder.rstrip(" .!?")}
            return {"action": "delete", "target": "latest"}

    if lowered.casefold() == "forget the last thing you remembered":
        return {"action": "delete", "target": "latest"}
    if lowered.casefold() in {"remove that memory", "delete that memory", "forget that memory", "forget memory"}:
        return {"action": "delete", "target": "latest"}

    return None
