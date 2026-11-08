"""Storage adapter verification tests for Tier 1, Tier 2, and Tier 3."""

import shutil
import tempfile
from uuid import uuid4
import pytest

from memory.core.models import Turn, TurnRole, FactItem, FactCategory, MemoryRecord
from memory.tiers.working.in_memory import InMemoryWorkingMemory
from memory.tiers.facts.sqlite_adapter import SQLiteFactStore
from memory.tiers.semantic.qdrant_adapter import QdrantAdapter
from memory.embeddings.embedder import LocalHashEmbedder


def test_tier1_in_memory_and_wal():
    """Verify in-memory working buffer and WAL disk replay."""
    temp_wal = tempfile.mkdtemp()
    try:
        mem1 = InMemoryWorkingMemory(wal_dir=temp_wal, enable_wal=True)
        session_id = "sess-123"
        user_id = "user-abc"

        turn1 = Turn(
            session_id=session_id,
            user_id=user_id,
            role=TurnRole.USER,
            content="Hello memory engine!",
        )
        turn2 = Turn(
            session_id=session_id,
            user_id=user_id,
            role=TurnRole.ASSISTANT,
            content="Hello! How can I help?",
        )
        mem1.append_turn(turn1)
        mem1.append_turn(turn2)

        window = mem1.get_active_window(session_id, limit=1)
        assert len(window) == 1
        assert window[0].content == "Hello! How can I help?"

        # Replay WAL on fresh instance pointing to same directory
        mem2 = InMemoryWorkingMemory(wal_dir=temp_wal, enable_wal=True)
        replayed = mem2.get_session_turns(session_id)
        assert len(replayed) == 2
        assert replayed[0].content == "Hello memory engine!"

        # Clear session
        mem2.clear(session_id)
        assert len(mem2.get_session_turns(session_id)) == 0
    finally:
        shutil.rmtree(temp_wal, ignore_errors=True)


def test_tier2_sqlite_versioning_and_invalidation():
    """Verify SQLiteFactStore schema, automatic versioning, and soft decay metrics."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        store = SQLiteFactStore(db_path=db_path)
        user_id = "alice"

        fact_v1 = FactItem(
            user_id=user_id,
            key="location",
            value="Berlin",
            category=FactCategory.FACT,
        )
        saved_v1 = store.put_fact(fact_v1)
        assert saved_v1.version == 1
        assert saved_v1.is_active is True

        # Query active fact
        active_fact = store.get_fact_by_key(user_id=user_id, key="location")
        assert active_fact is not None
        assert active_fact.value == "Berlin"

        # Update fact with new location -> version should increment to 2 and v1 marked inactive
        fact_v2 = FactItem(
            user_id=user_id,
            key="location",
            value="Tokyo",
            category=FactCategory.FACT,
        )
        saved_v2 = store.put_fact(fact_v2)
        assert saved_v2.version == 2
        assert saved_v2.is_active is True

        # Query active facts
        current = store.get_fact_by_key(user_id=user_id, key="location")
        assert current is not None
        assert current.value == "Tokyo"
        assert current.version == 2

        # Check that older fact v1 is marked inactive
        all_facts = store.get_facts(user_id=user_id, active_only=False)
        assert len(all_facts) == 2
        inactive_facts = [f for f in all_facts if not f.is_active]
        assert len(inactive_facts) == 1
        assert inactive_facts[0].value == "Berlin"
        assert inactive_facts[0].superseded_by == saved_v2.id

        # Touch fact
        initial_access = current.access_count
        store.touch_fact(current.id)
        updated = store.get_fact_by_key(user_id=user_id, key="location")
        assert updated.access_count == initial_access + 1

        # Invalidate fact
        store.invalidate_fact(current.id)
        assert store.get_fact_by_key(user_id=user_id, key="location") is None
    finally:
        import os
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_tier3_qdrant_vector_store():
    """Verify Qdrant vector upsert, query with payload filtering, and deletion."""
    embedder = LocalHashEmbedder(dim=128)
    adapter = QdrantAdapter(location=":memory:", collection_name="test_memories", dim=128)

    user1 = "user_one"
    user2 = "user_two"

    text1 = "Alice prefers Go for backend microservices"
    text2 = "Alice uses Postgres database"
    text3 = "Bob uses Rust for systems programming"

    rec1 = MemoryRecord(
        user_id=user1,
        text=text1,
        embedding=embedder.embed_text(text1),
    )
    rec2 = MemoryRecord(
        user_id=user1,
        text=text2,
        embedding=embedder.embed_text(text2),
    )
    rec3 = MemoryRecord(
        user_id=user2,
        text=text3,
        embedding=embedder.embed_text(text3),
    )

    ids = adapter.upsert_vectors([rec1, rec2, rec3])
    assert len(ids) == 3

    # Query for user1
    q_vec = embedder.embed_text("backend microservices and database")
    hits = adapter.query_similar(user_id=user1, query_embedding=q_vec, top_k=5)

    # Should only return user1 records
    assert len(hits) == 2
    for h in hits:
        assert h.user_id == user1

    # Delete record
    assert adapter.delete(rec1.id) is True
    hits_after = adapter.query_similar(user_id=user1, query_embedding=q_vec, top_k=5)
    assert len(hits_after) == 1
    assert hits_after[0].id == rec2.id
