"""Unit tests for LangMem Memory Adapter (Task 7.2)."""

import pytest
from cognitive.learning.langmem.langmem_adapter import (
    LangMemAdapter,
    MemoryItem,
)


def test_can_save_a_memory_and_recall_it_later():
    adapter = LangMemAdapter()

    # Save memory
    saved_item = adapter.save_memory(
        content="The user prefers dark mode and concise responses with bullet points.",
        user_id="user_charlie",
        memory_type="semantic",
        tags=["ui_preference", "style"],
    )
    assert saved_item.id.startswith("langmem_")
    assert saved_item.user_id == "user_charlie"

    # Save unrelated memory
    adapter.save_memory(
        content="System deployed on Kubernetes cluster with 8 nodes.",
        user_id="user_charlie",
        memory_type="episodic",
        tags=["infrastructure"],
    )

    # Search and recall
    results = adapter.search_memories(
        query="concise bullet points",
        user_id="user_charlie",
    )

    assert len(results) > 0
    top_match = results[0]
    assert "dark mode" in top_match.content
    assert top_match.id == saved_item.id


def test_extract_memories_from_conversation():
    adapter = LangMemAdapter()

    messages = [
        {"role": "user", "content": "Hello, how are you today?"},
        {"role": "assistant", "content": "I am operating optimally. How can I assist you?"},
        {"role": "user", "content": "Remember that I prefer using uv instead of standard pip for package installs."},
    ]

    extracted = adapter.extract_memories_from_messages(messages, user_id="user_dev")
    assert len(extracted) == 1
    assert "uv instead of standard pip" in extracted[0].content
    assert "user_preference" in extracted[0].tags
