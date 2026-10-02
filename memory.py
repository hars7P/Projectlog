"""Persistent local memory storage for JARVIS."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional


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
                "INSERT INTO memories (content) VALUES (?)",
                (memory,),
            )
        return memory

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

        normalized_query = query.casefold()
        query_terms = {
            part.casefold()
            for part in re.findall(r"[A-Za-z0-9']+", normalized_query)
            if part.strip()
        }
        if not query_terms:
            return memories[-limit:]

        expanded_terms = set(query_terms)
        if "me" in expanded_terms or "my" in expanded_terms or "i" in expanded_terms:
            expanded_terms |= {"me", "my", "i"}
        if "you" in expanded_terms or "your" in expanded_terms:
            expanded_terms |= {"you", "your"}

        relevant: List[str] = []
        for memory in memories:
            memory_text = memory.casefold()
            if any(term in memory_text for term in expanded_terms):
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
