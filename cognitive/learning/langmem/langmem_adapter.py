"""LangMem Memory Library Adapter (Task 7.2)

Provides conversation memory management tools to save, search, and recall
episodic and semantic memories during multi-turn agent interactions.
"""

from __future__ import annotations
import time
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryItem:
    """A remembered fact, user preference, or conversational episode."""
    id: str
    content: str
    user_id: str
    memory_type: str = "episodic"  # 'episodic', 'semantic', 'procedural'
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LangMemAdapter:
    """Manages conversational memory store, semantic recall, and extraction."""

    def __init__(self) -> None:
        self.memories: Dict[str, MemoryItem] = {}

    def save_memory(
        self,
        content: str,
        user_id: str = "default_user",
        memory_type: str = "episodic",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryItem:
        """Persist a new memory entry."""
        memory_id = f"langmem_{len(self.memories) + 1}_{int(time.time() * 1000) % 1000000}"
        item = MemoryItem(
            id=memory_id,
            content=content.strip(),
            user_id=user_id,
            memory_type=memory_type,
            tags=tags or [],
            timestamp=time.time(),
            metadata=metadata or {},
        )
        self.memories[memory_id] = item
        return item

    def search_memories(
        self,
        query: str,
        user_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[MemoryItem]:
        """Search and recall relevant memories matching the query."""
        query_terms = set(query.lower().split())
        scored: List[Tuple[float, MemoryItem]] = []

        for item in self.memories.values():
            if user_id and item.user_id != user_id:
                continue
            if memory_type and item.memory_type != memory_type:
                continue

            content_lower = item.content.lower()
            tags_lower = [t.lower() for t in item.tags]

            # Relevance scoring (keyword overlap + tags bonus + recency boost)
            matches = sum(1 for term in query_terms if term in content_lower or any(term in t for t in tags_lower))
            if matches > 0:
                recency_hours = (time.time() - item.timestamp) / 3600.0
                recency_boost = 1.0 / (1.0 + math.log1p(max(0.0, recency_hours)))
                score = (matches * 2.0) + (0.5 * recency_boost)
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def extract_memories_from_messages(
        self,
        messages: List[Dict[str, str]],
        user_id: str = "default_user",
    ) -> List[MemoryItem]:
        """Automatically identify and extract persistent preferences or key facts from messages."""
        extracted: List[MemoryItem] = []
        for msg in messages:
            content = msg.get("content", "")
            lower = content.lower()
            if any(cue in lower for cue in ["i prefer", "my favorite", "remember that", "always use", "never use"]):
                item = self.save_memory(
                    content=content,
                    user_id=user_id,
                    memory_type="semantic",
                    tags=["user_preference", "auto_extracted"],
                )
                extracted.append(item)
        return extracted

    def delete_memory(self, memory_id: str) -> bool:
        """Remove a memory by ID."""
        if memory_id in self.memories:
            del self.memories[memory_id]
            return True
        return False

