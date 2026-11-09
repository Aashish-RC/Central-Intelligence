"""Unit and integration tests for Versioned Memory Snapshots and Rollback (Feature 2.51)."""

import tempfile
import pytest
from memory.config import (
    MemoryConfig,
    WorkingMemoryBackend,
    FactStoreBackend,
    VectorStoreBackend,
    EmbeddingBackend,
)
from memory.engine import MemoryEngine
from memory.lessons.models import LessonRecord, LessonCategory
from memory.core.models import FactItem


@pytest.fixture
def memory_fixture():
    wal_dir = tempfile.mkdtemp()
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()

    config = MemoryConfig(
        working_backend=WorkingMemoryBackend.IN_MEMORY,
        wal_dir=wal_dir,
        fact_backend=FactStoreBackend.SQLITE,
        sqlite_path=db_path,
        vector_backend=VectorStoreBackend.QDRANT,
        qdrant_location=":memory:",
        embedding_backend=EmbeddingBackend.LOCAL,
        collection_name="test_snapshot_coll",
    )
    engine = MemoryEngine(config=config)
    yield engine


def test_create_and_list_memory_snapshots(memory_fixture):
    engine = memory_fixture
    user_id = "user_snap_1"

    # Add initial fact
    engine.facts.put_fact(
        FactItem(user_id=user_id, key="api_port", value="8000")
    )

    # Capture snapshot
    snap = engine.create_memory_snapshot(
        user_id=user_id,
        tag="v1.0-clean",
        description="Initial clean setup",
    )

    assert snap.id.startswith("snap_")
    assert snap.tag == "v1.0-clean"
    assert len(snap.facts) == 1
    assert snap.facts[0].key == "api_port"

    # Verify listing
    snapshots = engine.list_memory_snapshots(user_id=user_id)
    assert len(snapshots) >= 1
    assert snapshots[0].id == snap.id


def test_rollback_memory_adaptation_restores_prior_state(memory_fixture):
    engine = memory_fixture
    user_id = "user_rollback"

    # 1. Base state: 1 fact, 1 lesson
    engine.facts.put_fact(
        FactItem(user_id=user_id, key="database_type", value="PostgreSQL")
    )
    lesson_1 = LessonRecord(
        lesson_id="lesson_base",
        title="API Timeout Guideline",
        rule="Always specify timeout when connecting to external APIs",
        mistake="Infinite hanging connection",
        resolution="Set timeout to 30s",
        trigger_context="api network requests",
        category=LessonCategory.SAFETY_RULE,
        confidence=0.9,
    )
    engine.lesson_store.save_lesson(lesson_1)

    # 2. Checkpoint Snapshot A
    snap_a = engine.create_memory_snapshot(user_id=user_id, tag="checkpoint-A")

    # 3. Apply unwanted adaptations / hallucinations
    engine.facts.put_fact(
        FactItem(user_id=user_id, key="database_type", value="Unwanted_MongoDB")
    )
    engine.facts.put_fact(
        FactItem(user_id=user_id, key="poisoned_belief", value="FakeFact")
    )
    lesson_bad = LessonRecord(
        lesson_id="lesson_bad",
        title="Bad Indexing Advice",
        rule="Never use indexes on tables",
        mistake="Misguided optimization",
        resolution="Revert index omission",
        trigger_context="database query",
        category=LessonCategory.USER_CORRECTION,
        confidence=0.8,
    )
    engine.lesson_store.save_lesson(lesson_bad)

    # Verify state was mutated (database_type updated + poisoned_belief added)
    current_facts = engine.facts.get_facts(user_id=user_id)
    assert len(current_facts) == 2
    assert any(f.value == "Unwanted_MongoDB" for f in current_facts)
    all_lessons = engine.lesson_store.query_lessons(query="", limit=10)
    assert len(all_lessons) == 2

    # 4. Rollback to Checkpoint A
    result = engine.rollback_memory(user_id=user_id, snapshot_id=snap_a.id)

    assert result.success is True
    assert result.facts_removed >= 1  # Unwanted facts invalidated/removed
    assert result.lessons_removed == 1  # The bad lesson removed

    # Verify active facts after rollback
    restored_facts = engine.facts.get_facts(user_id=user_id)
    assert len(restored_facts) == 1
    assert restored_facts[0].value == "PostgreSQL"

    # Verify lessons after rollback
    restored_lessons = engine.lesson_store.query_lessons(query="", limit=10)
    assert len(restored_lessons) == 1
    assert restored_lessons[0].lesson_id == "lesson_base"


def test_rollback_rejects_unauthorized_user(memory_fixture):
    engine = memory_fixture
    snap = engine.create_memory_snapshot(user_id="user_owner", tag="owner_snap")

    # Another user attempts to rollback
    result = engine.rollback_memory(user_id="user_intruder", snapshot_id=snap.id)
    assert result.success is False
    assert "Access denied" in result.message
