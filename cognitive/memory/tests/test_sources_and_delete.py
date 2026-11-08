"""Tests for Step 13: Memory Sources view, project isolation, and granular deletion."""

import os
from uuid import UUID
import pytest
from memory.core.models import TurnRole
from memory.engine import MemoryEngine
from memory.config import MemoryConfig, WorkingMemoryBackend, FactStoreBackend, VectorStoreBackend


@pytest.fixture
def clean_engine(tmp_path):
    sqlite_db = str(tmp_path / "test_facts.db")
    qdrant_loc = ":memory:"
    config = MemoryConfig(
        working_backend=WorkingMemoryBackend.IN_MEMORY,
        fact_backend=FactStoreBackend.SQLITE,
        vector_backend=VectorStoreBackend.QDRANT,
        sqlite_path=sqlite_db,
        qdrant_location=qdrant_loc,
        embedder_type="hash",
    )
    return MemoryEngine(config=config)


def test_project_id_isolation(clean_engine):
    """Memories stored in project-A should not leak into project-B."""
    user = "alice"
    
    # Store memory in Project Alpha
    clean_engine.remember(
        user_id=user,
        text="My preferred database for this project is PostgreSQL and Python.",
        project_id="proj_alpha",
    )

    # Store memory in Project Beta
    clean_engine.remember(
        user_id=user,
        text="In this project we strictly use Go and MongoDB.",
        project_id="proj_beta",
    )

    # Recall in proj_alpha
    ctx_alpha = clean_engine.recall(user_id=user, query="database stack", project_id="proj_alpha")
    assert "proj_alpha" in ctx_alpha.context_str or "PostgreSQL" in ctx_alpha.context_str or len(ctx_alpha.facts) > 0
    # proj_alpha facts should not contain MongoDB
    for f in ctx_alpha.facts:
        assert "MongoDB" not in f.value

    # Recall in proj_beta
    ctx_beta = clean_engine.recall(user_id=user, query="database stack", project_id="proj_beta")
    for f in ctx_beta.facts:
        assert "PostgreSQL" not in f.value


def test_memory_sources_view_provenance(clean_engine):
    """Memory sources view should expose all facts, archival items, and provenance metadata."""
    user = "bob"
    proj = "proj_webapp"

    rem = clean_engine.remember(
        user_id=user,
        text="I love dark mode UI and TypeScript.",
        session_id="sess_123",
        project_id=proj,
    )

    sources_view = clean_engine.get_memory_sources(user_id=user, project_id=proj)
    assert sources_view.project_id == proj
    assert sources_view.user_id == user
    assert sources_view.total_sources >= 1

    # Check provenance on items
    for item in sources_view.items:
        assert item.provenance is not None
        assert item.provenance.confidence > 0.0
        assert item.provenance.source_type in ["user_turn", "inferred_fact", "archival_vector"]
        assert item.project_id == proj


def test_fact_update_and_versioning(clean_engine):
    """Updating a fact should increment its version and change value."""
    user = "charlie"
    proj = "proj_crm"

    clean_engine.remember(
        user_id=user,
        text="My preferred language is Python.",
        project_id=proj,
    )

    facts = clean_engine.get_active_facts(user_id=user, project_id=proj)
    assert len(facts) >= 1
    target_fact = facts[0]
    original_ver = target_fact.version

    # Update fact
    updated = clean_engine.update_fact(target_fact.id, "Rust")
    assert updated is not None
    assert updated.value == "Rust"
    assert updated.version == original_ver + 1

    # Verify recalled fact reflects new value
    recalled_facts = clean_engine.get_active_facts(user_id=user, project_id=proj)
    matching = [f for f in recalled_facts if f.id == target_fact.id]
    assert len(matching) == 1
    assert matching[0].value == "Rust"


def test_fact_deletion_done_when_recalled_and_deleted(clean_engine):
    """Core Step 13 requirement: Done when: It recalls context and you can delete it."""
    user = "david"
    proj = "proj_api"

    # Step 1: Remember context
    rem_res = clean_engine.remember(
        user_id=user,
        text="My favorite cloud provider is AWS.",
        session_id="sess_cloud",
        project_id=proj,
    )

    # Step 2: It recalls context
    ctx = clean_engine.recall(user_id=user, query="cloud provider", session_id="sess_cloud", project_id=proj)
    assert ctx.total_tokens > 0
    facts_before = clean_engine.get_active_facts(user_id=user, project_id=proj)
    assert len(facts_before) >= 1
    fact_id = facts_before[0].id

    # Step 3: Delete it
    deleted = clean_engine.delete_fact(fact_id)
    assert deleted is True

    # Step 4: Verify it is no longer recalled
    facts_after = clean_engine.get_active_facts(user_id=user, project_id=proj)
    remaining_ids = [f.id for f in facts_after]
    assert fact_id not in remaining_ids


def test_delete_archival_and_delete_all_user_memory(clean_engine):
    """Deleting archival record and wiping all user memory cleanly."""
    user = "eve"
    proj = "proj_security"

    rem = clean_engine.remember(
        user_id=user,
        text="The admin token is refreshed every 12 hours.",
        session_id="sess_sec",
        project_id=proj,
    )

    archival_id = rem.get("archival_record_id")
    if archival_id:
        # Delete specific archival vector
        del_vec = clean_engine.delete_archival_memory(UUID(archival_id))
        assert del_vec is True

    # Wipe all user memory
    wipe_res = clean_engine.delete_all_user_memory(user_id=user)
    assert wipe_res["deleted_facts"] >= 0

    sources = clean_engine.get_memory_sources(user_id=user, project_id=proj)
    assert sources.facts_count == 0
