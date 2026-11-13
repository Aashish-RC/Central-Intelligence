"""Storage adapter verification tests for Tier 1, Tier 2, and Tier 3."""

import shutil
import tempfile
from uuid import uuid4
import pytest

from memory.core.models import Turn, TurnRole, FactItem, FactCategory, MemoryRecord
from memory.tiers.working.in_memory import InMemoryWorkingMemory
from memory.tiers.facts.sqlite_adapter import SQLiteFactStore
from memory.tiers.facts.postgres_adapter import (
    PostgreSQLFactStore,
    _Pg8000DictCursor,
    _Pg8000ConnectionWrapper,
)
from memory.core.exceptions import AdapterConnectionError
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


def test_tier2_postgres_pg8000_cursor_and_wrapper():
    """Verify pg8000 dict cursor and connection wrapper compatibility."""
    class DummyRawCursor:
        def __init__(self):
            self.description = [("id", None), ("user_id", None), ("key", None), ("value", None)]
            self.rowcount = 1
            self.closed = False
            self.executed = []

        def execute(self, op, params=None):
            self.executed.append((op, params))

        def executemany(self, op, seq):
            for p in seq:
                self.executed.append((op, p))

        def fetchone(self):
            return ("uuid-1", "user-a", "theme", "dark")

        def fetchall(self):
            return [("uuid-1", "user-a", "theme", "dark"), ("uuid-2", "user-a", "lang", "en")]

        def close(self):
            self.closed = True

    raw = DummyRawCursor()
    dict_cur = _Pg8000DictCursor(raw)
    assert dict_cur.rowcount == 1

    # fetchone mapping
    one = dict_cur.fetchone()
    assert one == {"id": "uuid-1", "user_id": "user-a", "key": "theme", "value": "dark"}

    # fetchall mapping
    all_rows = dict_cur.fetchall()
    assert len(all_rows) == 2
    assert all_rows[0]["key"] == "theme"
    assert all_rows[1]["key"] == "lang"

    # Context manager and close
    with _Pg8000DictCursor(raw) as cur:
        assert cur.rowcount == 1
    assert raw.closed is True

    # Wrapper delegation
    class DummyRawConn:
        def __init__(self):
            self.committed = False
            self.rolled_back = False
            self.closed = False

        def cursor(self):
            return DummyRawCursor()

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    dummy_conn = DummyRawConn()
    wrapped_conn = _Pg8000ConnectionWrapper(dummy_conn)
    cur = wrapped_conn.cursor()
    assert isinstance(cur, _Pg8000DictCursor)
    wrapped_conn.commit()
    assert dummy_conn.committed is True
    wrapped_conn.rollback()
    assert dummy_conn.rolled_back is True
    wrapped_conn.close()
    assert dummy_conn.closed is True


def test_tier2_postgres_fact_store_connection_guard():
    """Verify PostgreSQLFactStore enforces configuration and fails with AdapterConnectionError."""
    # Unconfigured URL
    store = PostgreSQLFactStore(connection_url=None)
    with pytest.raises(AdapterConnectionError, match="connection URL is not configured"):
        store._get_connection()

    # Invalid connection URL fails closed
    store_bad = PostgreSQLFactStore.__new__(PostgreSQLFactStore)
    store_bad._url = "postgresql://invalid_host_unreachable:9999/nodb"
    store_bad._pool = None
    with pytest.raises(AdapterConnectionError):
        store_bad._get_connection()


def test_tier2_postgres_fact_store_operations_mocked():
    """Verify PostgreSQLFactStore serialization and fact conversion."""
    store = PostgreSQLFactStore(connection_url=None)

    raw_dict = {
        "id": "11111111-1111-1111-1111-111111111111",
        "user_id": "alice",
        "key": "framework",
        "value": "FastAPI",
        "category": "preference",
        "source_event_id": "evt-001",
        "version": 1,
        "is_active": True,
        "confidence_score": 0.95,
        "superseded_by": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "last_accessed_at": "2026-01-01T00:00:00Z",
        "access_count": 3,
    }

    fact = store._dict_to_fact(raw_dict)
    assert str(fact.id) == "11111111-1111-1111-1111-111111111111"
    assert fact.user_id == "alice"
    assert fact.key == "framework"
    assert fact.value == "FastAPI"
    assert fact.category == FactCategory.PREFERENCE
    assert fact.version == 1
    assert fact.is_active is True
    assert fact.access_count == 3

