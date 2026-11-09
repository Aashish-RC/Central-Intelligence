"""Tests for Memory Access Control Bridge (Task 12.12, Feature 2.38 — DEF-01 UNBLOCKED)."""

import pytest
from memory.access_control.openfga_bridge import (
    AccessDeniedError,
    check_memory_access,
)
from control.identity.openfga_adapter import OpenFGAAdapter


def test_memory_access_control_rebac_acceptance():
    """Acceptance Test: Alice cannot recall Bob's memory; Bob's admin can recall Bob's memory."""
    fga = OpenFGAAdapter()

    # Bob's admin is granted admin relation on Bob's memory
    fga.write_tuple(user="user:bob_admin", relation="admin", object="memory:bob")

    # 1. Alice attempts to recall Bob's memory -> Access Denied
    with pytest.raises(AccessDeniedError, match="cannot read memory scope bob"):
        check_memory_access(
            user_id="alice",
            action="read",
            memory_scope="bob",
            openfga_client=fga,
        )

    # 2. Bob's admin recalls Bob's memory -> Allowed
    assert check_memory_access(
        user_id="bob_admin",
        action="read",
        memory_scope="bob",
        openfga_client=fga,
    ) is True

    # 3. Bob himself can read/write his own memory (self-access)
    assert check_memory_access(
        user_id="bob",
        action="read",
        memory_scope="bob",
        openfga_client=fga,
    ) is True
    assert check_memory_access(
        user_id="bob",
        action="write",
        memory_scope="bob",
        openfga_client=fga,
    ) is True

    # 4. Alice attempts to write into Bob's memory -> Access Denied
    with pytest.raises(AccessDeniedError, match="cannot write memory scope bob"):
        check_memory_access(
            user_id="alice",
            action="write",
            memory_scope="bob",
            openfga_client=fga,
        )


def test_engine_integration_access_control(tmp_path):
    """Verify MemoryEngine.remember and MemoryEngine.recall enforce access control."""
    from memory.engine import MemoryEngine
    from memory.config import (
        MemoryConfig,
        WorkingMemoryBackend,
        FactStoreBackend,
        VectorStoreBackend,
        EmbeddingBackend,
    )

    wal_dir = str(tmp_path / "wal")
    db_path = str(tmp_path / "sqlite.db")
    cfg = MemoryConfig(
        working_backend=WorkingMemoryBackend.IN_MEMORY,
        wal_dir=wal_dir,
        fact_backend=FactStoreBackend.SQLITE,
        sqlite_path=db_path,
        vector_backend=VectorStoreBackend.QDRANT,
        qdrant_location=":memory:",
        memgraph_host=":memory:",
        embedding_backend=EmbeddingBackend.LOCAL,
        embedding_dim=128,
        max_context_tokens=500,
    )
    engine = MemoryEngine(config=cfg)

    # Bob writing his own memory should succeed
    engine.remember(
        text="Bob secret plans",
        user_id="bob",
        metadata={"target_memory_scope": "bob"}
    )

    # Alice trying to write into Bob's scope fails
    with pytest.raises(AccessDeniedError):
        engine.remember(
            text="Alice injects into Bob",
            user_id="alice",
            metadata={"target_memory_scope": "bob"}
        )

    # Alice trying to recall Bob's scope fails
    with pytest.raises(AccessDeniedError):
        engine.recall(
            query="plans",
            user_id="alice",
            target_memory_scope="bob"
        )

    # Bob recalling his own scope succeeds
    pkg = engine.recall(
        query="plans",
        user_id="bob"
    )
    assert pkg is not None


if __name__ == "__main__":
    print("Running test_memory_access_control_rebac_acceptance...")
    test_memory_access_control_rebac_acceptance()
    print("test_memory_access_control_rebac_acceptance PASSED!")
    import pathlib
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        print("Running test_engine_integration_access_control...")
        test_engine_integration_access_control(pathlib.Path(td))
        print("test_engine_integration_access_control PASSED!")
