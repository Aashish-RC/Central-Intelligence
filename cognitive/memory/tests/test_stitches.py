"""Unit tests for the 4 Operational Stitches and Autonomous Consolidation."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest

from memory.core.models import FactItem, FactCategory, Turn, TurnRole, MemoryRecord, utc_now
from memory.stitches.extractor import FactExtractor
from memory.stitches.conflict_resolver import ConflictResolver
from memory.stitches.synthesizer import ContextSynthesizer
from memory.stitches.consolidation import ConsolidationEngine
from memory.tiers.facts.sqlite_adapter import SQLiteFactStore
from memory.tiers.working.in_memory import InMemoryWorkingMemory
from memory.tiers.semantic.qdrant_adapter import QdrantAdapter
from memory.embeddings.embedder import LocalHashEmbedder
from memory.config import MemoryConfig


def test_extractor_stitch():
    """Verify rule-based and structured extraction for facts, contradictions, and chit-chat filtering."""
    extractor = FactExtractor()
    user_id = "test_user"

    # Chit-chat should yield no facts and no archival text
    plan_chat = extractor.extract_memory_plan("Hello! How are you doing today?", user_id=user_id)
    assert len(plan_chat.facts_to_add) == 0
    assert plan_chat.archival_text is None

    # Location switch statement
    plan_move = extractor.extract_memory_plan("I moved from Berlin to Tokyo last week", user_id=user_id)
    assert len(plan_move.facts_to_add) >= 1
    loc_fact = next((f for f in plan_move.facts_to_add if f.key == "location"), None)
    assert loc_fact is not None
    assert "Tokyo" in loc_fact.value
    assert "location" in plan_move.keys_to_invalidate

    # Programming language statement
    plan_lang = extractor.extract_memory_plan("I only write Go code now, dropped Rust.", user_id=user_id)
    lang_fact = next((f for f in plan_lang.facts_to_add if f.key == "preferred_language"), None)
    assert lang_fact is not None
    assert lang_fact.value == "Go"


def test_conflict_resolver_stitch():
    """Verify deduplication and contradiction resolution against active facts."""
    fact_store = SQLiteFactStore(db_path=":memory:")
    resolver = ConflictResolver(fact_store=fact_store)
    user_id = "user_456"

    # Insert initial fact: location Berlin
    initial = [
        FactItem(
            user_id=user_id,
            key="location",
            value="Berlin",
            category=FactCategory.FACT,
        )
    ]
    saved1 = resolver.resolve_and_apply(initial)
    assert len(saved1) == 1
    assert saved1[0].value == "Berlin"
    assert saved1[0].version == 1

    # Insert identical fact -> deduplicated without incrementing version
    duplicate = [
        FactItem(
            user_id=user_id,
            key="location",
            value="Berlin",
            category=FactCategory.FACT,
        )
    ]
    saved_dup = resolver.resolve_and_apply(duplicate)
    assert len(saved_dup) == 1
    assert saved_dup[0].version == 1

    # Insert contradiction: location Tokyo
    contradiction = [
        FactItem(
            user_id=user_id,
            key="location",
            value="Tokyo",
            category=FactCategory.FACT,
        )
    ]
    saved2 = resolver.resolve_and_apply(contradiction, keys_to_invalidate=["location"])
    assert len(saved2) == 1
    assert saved2[0].value == "Tokyo"
    assert saved2[0].version == 2

    # Verify Berlin was marked superseded
    active = fact_store.get_facts(user_id=user_id, active_only=True)
    assert len(active) == 1
    assert active[0].value == "Tokyo"

    all_facts = fact_store.get_facts(user_id=user_id, active_only=False)
    assert len(all_facts) == 2
    superseded = [f for f in all_facts if not f.is_active]
    assert len(superseded) == 1
    assert superseded[0].value == "Berlin"
    assert superseded[0].superseded_by == saved2[0].id


def test_synthesizer_token_budget_enforcement():
    """Verify that synthesized context never exceeds max_context_tokens."""
    config = MemoryConfig(max_context_tokens=150)
    synthesizer = ContextSynthesizer(config=config)

    user_id = "alice"
    session_id = "sess_budget"

    turns = [
        Turn(
            session_id=session_id,
            user_id=user_id,
            role=TurnRole.USER,
            content=f"This is an extensive conversational turn number {i} discussing software architecture in detail." * 3,
        )
        for i in range(20)
    ]

    facts = [
        FactItem(user_id=user_id, key=f"pref_{i}", value=f"val_{i}", category=FactCategory.PREFERENCE)
        for i in range(5)
    ]

    memories = [
        MemoryRecord(user_id=user_id, text=f"Archival memory snippet {i} with long descriptive context.")
        for i in range(5)
    ]

    pkg = synthesizer.synthesize(
        user_id=user_id,
        session_id=session_id,
        working_turns=turns,
        core_facts=facts,
        archival_memories=memories,
    )

    assert pkg.token_count <= 150
    assert "<agent_memory_context>" in pkg.formatted_prompt
    assert "</agent_memory_context>" in pkg.formatted_prompt


def test_consolidation_engine_rem_sleep():
    """Verify consolidation compresses session turns into Tier 3 milestone and purges Tier 1."""
    working = InMemoryWorkingMemory(enable_wal=False)
    facts = SQLiteFactStore(db_path=":memory:")
    vectors = QdrantAdapter(location=":memory:", collection_name="test_consolidation", dim=128)
    embedder = LocalHashEmbedder(dim=128)

    engine = ConsolidationEngine(
        working_memory=working,
        fact_store=facts,
        vector_store=vectors,
        embedder=embedder,
    )

    user_id = "bob"
    session_id = "sess_rem_test"

    for i in range(15):
        working.append_turn(
            Turn(
                session_id=session_id,
                user_id=user_id,
                role=TurnRole.USER if i % 2 == 0 else TurnRole.ASSISTANT,
                content=f"Message {i}: working through complex memory design requirements.",
            )
        )

    assert len(working.get_session_turns(session_id)) == 15

    # Run consolidation cycle
    result = engine.consolidate_session(user_id=user_id, session_id=session_id)
    assert result.turns_consolidated == 15
    assert result.purged_from_working is True

    # Tier 1 cache should be cleared
    assert len(working.get_session_turns(session_id)) == 0

    # Tier 3 vector store should have milestone record
    q_vec = embedder.embed_text("complex memory design requirements")
    hits = vectors.query_similar(user_id=user_id, query_embedding=q_vec, top_k=5)
    assert len(hits) >= 1
    assert "Session sess_rem_test recap" in hits[0].text


def test_decay_scoring_formula():
    """Verify decay calculation prioritizes recent and frequently accessed memories."""
    engine = ConsolidationEngine(
        working_memory=InMemoryWorkingMemory(enable_wal=False),
        fact_store=SQLiteFactStore(db_path=":memory:"),
        vector_store=QdrantAdapter(location=":memory:", collection_name="test_decay", dim=128),
        embedder=LocalHashEmbedder(dim=128),
    )

    now = utc_now()
    two_weeks_ago = now - timedelta(days=14)

    # Fresh memory with 0 accesses
    fresh_score = engine.calculate_decay_score(last_accessed_at=now, access_count=0, half_life_days=14.0)
    # Old memory with 0 accesses
    old_score = engine.calculate_decay_score(last_accessed_at=two_weeks_ago, access_count=0, half_life_days=14.0)

    # After 1 half-life (14 days), decay is roughly half
    assert old_score < fresh_score
    assert pytest.approx(old_score / fresh_score, rel=0.1) == 0.5

    # High frequency access reinforces memory against decay
    frequent_old_score = engine.calculate_decay_score(last_accessed_at=two_weeks_ago, access_count=10, half_life_days=14.0)
    assert frequent_old_score > old_score
