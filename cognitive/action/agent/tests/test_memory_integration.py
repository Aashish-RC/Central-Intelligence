"""Test suite for 3-tier memory persistence, fact extraction, and semantic recall."""

import os
import pytest
from agent.memory.manager import MemoryManager
from agent.memory.tiers.working import WorkingMemoryTier
from agent.memory.tiers.facts import FactStoreTier
from agent.memory.tiers.vector import VectorMemoryTier


@pytest.fixture
def memory_manager(tmp_path):
    db_file = str(tmp_path / "test_facts.db")
    wal_dir = str(tmp_path / "wal")
    working = WorkingMemoryTier(wal_dir=wal_dir)
    facts = FactStoreTier(db_path=db_file)
    vector = VectorMemoryTier()
    return MemoryManager(working=working, facts=facts, vector=vector)


@pytest.mark.asyncio
async def test_remember_and_fact_extraction(memory_manager):
    session_id = "test_sess_01"
    ns = "tenant_test"

    # User states a rule and a preference
    text = "Please note: My name is Alice and never use plain text credentials."
    res = await memory_manager.remember(
        session_id=session_id,
        role="user",
        content=text,
        namespace=ns,
    )

    assert res["extracted_facts"] >= 1
    assert res["vector_indexed"] is True

    # Query facts
    stored = memory_manager.facts.query_facts(namespace=ns)
    assert len(stored) >= 1
    assert any("Alice" in f["fact_text"] or "credentials" in f["fact_text"] for f in stored)


@pytest.mark.asyncio
async def test_cross_session_recall(memory_manager):
    ns = "tenant_cross_session"

    # Session 1: User sets constraint
    await memory_manager.remember(
        session_id="session_1",
        role="user",
        content="Policy: All external network requests must use TLS 1.3.",
        namespace=ns,
    )

    # Session 2: Fresh session queries context
    context = await memory_manager.recall(
        query="network security requirements",
        namespace=ns,
        session_id="session_2",
    )

    # Core facts from Session 1 should be recalled
    assert len(context.core_facts) >= 1
    prompt_str = context.to_system_prompt_section()
    assert "TLS 1.3" in prompt_str
