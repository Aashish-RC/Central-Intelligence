"""End-to-end integration and verification tests for the Unified MemoryEngine."""

import tempfile
import shutil
import pytest

from memory.engine import MemoryEngine
from memory.config import MemoryConfig, WorkingMemoryBackend, FactStoreBackend, VectorStoreBackend, EmbeddingBackend
from memory.core.models import TurnRole


@pytest.fixture
def temp_engine():
    """Create a fully isolated local MemoryEngine using temporary directories and in-memory stores."""
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
        embedding_dim=128,
        max_context_tokens=500,
    )
    engine = MemoryEngine(config=config)

    yield engine

    shutil.rmtree(wal_dir, ignore_errors=True)
    import os
    try:
        os.remove(db_path)
    except OSError:
        pass


def test_verification_1_attribution_and_identity(temp_engine):
    """Test 1: Agent recalls user name, tech stack, and constraints across sessions."""
    user_id = "alice_dev"

    # Turn 1: User introduces name and preferences
    res1 = temp_engine.remember(
        user_id=user_id,
        text="My name is Alice and I am a backend software engineer.",
        session_id="session_1",
    )
    assert res1["user_id"] == user_id

    # Turn 2: User sets tech stack
    temp_engine.remember(
        user_id=user_id,
        text="I only write Go code now, dropped Rust.",
        session_id="session_1",
    )

    # Query in a brand new session
    context = temp_engine.recall(
        user_id=user_id,
        query="What language and tools does Alice use?",
        session_id="session_2",
    )

    prompt = context.formatted_prompt
    assert "preferred_language: Go" in prompt
    assert "name: Alice" in prompt
    assert context.token_count <= 500


def test_verification_2_contradiction_resolution(temp_engine):
    """Test 2: When user says 'I moved from Berlin to Tokyo', query returns Tokyo,
    and Berlin is marked superseded in ground-truth facts.
    """
    user_id = "traveler_bob"

    # Step 1: User lives in Berlin
    temp_engine.remember(
        user_id=user_id,
        text="I live in Berlin right now.",
        session_id="sess_init",
    )

    facts1 = temp_engine.get_active_facts(user_id=user_id)
    assert any(f.key == "location" and "Berlin" in f.value for f in facts1)

    # Step 2: User announces relocation to Tokyo
    temp_engine.remember(
        user_id=user_id,
        text="I moved from Berlin to Tokyo last week.",
        session_id="sess_relocate",
    )

    # Ground-truth check
    facts2 = temp_engine.get_active_facts(user_id=user_id)
    active_locs = [f for f in facts2 if f.key == "location"]
    assert len(active_locs) == 1
    assert "Tokyo" in active_locs[0].value
    assert active_locs[0].version == 2

    # Query recall
    pkg = temp_engine.recall(user_id=user_id, query="Where do I live?", session_id="sess_relocate")
    assert "location: Tokyo" in pkg.formatted_prompt
    assert "Berlin" not in [f.value for f in pkg.core_facts if f.key == "location"]


def test_verification_3_token_budget_boundary(temp_engine):
    """Test 3: Injected context never exceeds the configured token threshold (500 tokens)
    regardless of session length and turns.
    """
    user_id = "chatter_user"
    session_id = "long_session"

    # Flood working session with 50 lengthy turns
    for i in range(50):
        temp_engine.remember(
            user_id=user_id,
            text=f"Turn {i}: Let's analyze architectural tradeoffs between event-driven microservices and monolithic architectures with extensive explanations." * 3,
            session_id=session_id,
            role=TurnRole.USER if i % 2 == 0 else TurnRole.ASSISTANT,
        )

    # Recall context
    pkg = temp_engine.recall(
        user_id=user_id,
        query="What was our discussion on architectures?",
        session_id=session_id,
    )

    assert pkg.token_count <= 500
    assert pkg.token_count > 0
    assert "<agent_memory_context>" in pkg.formatted_prompt


def test_verification_4_offline_capability():
    """Test 4: Entire system initializes and executes offline using local hash embeddings,
    SQLite, and Qdrant in-memory without external services.
    """
    config = MemoryConfig(
        working_backend=WorkingMemoryBackend.IN_MEMORY,
        fact_backend=FactStoreBackend.SQLITE,
        sqlite_path=":memory:",
        vector_backend=VectorStoreBackend.QDRANT,
        qdrant_location=":memory:",
        embedding_backend=EmbeddingBackend.LOCAL,
        embedding_dim=64,
        openai_api_key=None,
    )
    engine = MemoryEngine(config=config)

    # Offline remember & recall
    res = engine.remember(user_id="offline_user", text="I use Linux on my laptop.", session_id="s1")
    assert res["event_id"] is not None

    pkg = engine.recall(user_id="offline_user", query="What OS do I use?", session_id="s1")
    assert "operating_system: Linux" in pkg.formatted_prompt
    assert pkg.token_count <= 500


def test_session_consolidation_workflow(temp_engine):
    """Test consolidation workflow: session turns compressed to Tier 3 milestone and working cache purged."""
    user_id = "user_milestone"
    session_id = "s_complete"

    for i in range(10):
        temp_engine.remember(
            user_id=user_id,
            text=f"Step {i}: Configured database migrations and CI pipelines.",
            session_id=session_id,
        )

    # Consolidate
    c_res = temp_engine.consolidate(user_id=user_id, session_id=session_id)
    assert c_res.turns_consolidated == 10
    assert c_res.purged_from_working is True

    # Tier 1 working turns should now be empty for that session
    assert len(temp_engine.working.get_session_turns(session_id)) == 0

    # Recalling in new session should still retrieve the milestone via Tier 3
    recalled = temp_engine.recall(user_id=user_id, query="CI pipeline database", session_id="s_next")
    assert len(recalled.archival_matches) > 0


def test_qdrant_adapter_health_and_retrieval():
    """
    Validates Task O1: Qdrant adapter connection health check and vector indexing.
    """
    from memory.embeddings.qdrant_adapter import QdrantAdapter
    from memory.core.models import MemoryRecord, utc_now
    from uuid import uuid4

    adapter = QdrantAdapter(location=":memory:", collection_name="test_health_col", dim=128)
    # 1. Connection health check
    assert adapter.check_health() is True

    # 2. Vector indexing
    rec = MemoryRecord(
        id=uuid4(),
        user_id="user_qdrant_test",
        text="Specialist in distributed consensus algorithms and Paxos.",
        embedding=[0.1] * 128,
        confidence_score=0.98,
        created_at=utc_now(),
        updated_at=utc_now(),
        last_accessed_at=utc_now(),
    )
    upserted = adapter.upsert_vectors([rec])
    assert len(upserted) == 1
    assert upserted[0] == rec.id

    # 3. Vector query
    matches = adapter.query_similar(
        user_id="user_qdrant_test",
        query_embedding=[0.1] * 128,
        top_k=3,
    )
    assert len(matches) == 1
    assert matches[0].text == "Specialist in distributed consensus algorithms and Paxos."

