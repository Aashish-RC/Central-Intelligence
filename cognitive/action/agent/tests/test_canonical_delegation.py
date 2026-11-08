"""
Verification tests for Category B Canonical Subsystem Integration:
1. Agent Sandbox Canonicalization (AgentRunner -> sandboxes.manager.SandboxManager)
2. Agent Memory Canonicalization (MemoryManager -> memory.engine.MemoryEngine)
"""

import pytest
from unittest.mock import MagicMock


from agent.core.manifest import AgentManifest, AgentMetadata, RuntimeConfig, SandboxConfig, ToolDefinition
from agent.executor.runner import AgentRunner
from agent.memory.manager import MemoryManager
from agent.memory.tiers.working import WorkingMemoryTier
from agent.memory.tiers.facts import FactStoreTier
from agent.memory.tiers.vector import VectorMemoryTier
from sandboxes.manager import SandboxManager
from memory.engine import MemoryEngine


@pytest.mark.asyncio
async def test_agent_runner_uses_canonical_sandbox_manager():
    """Verify AgentRunner delegates to canonical SandboxManager and invokes security governor."""
    manifest = AgentManifest(
        agent_id="test-canonical-runner",
        metadata=AgentMetadata(name="Canonical Runner"),
        runtime=RuntimeConfig(model="mock-model"),
        sandbox=SandboxConfig(provider="local"),
        tools=[
            ToolDefinition(
                name="run_script",
                type="sandbox_command",
                command="echo 'canonical-sandbox-exec'",
            )
        ],
    )

    runner = AgentRunner(manifest=manifest)
    assert isinstance(runner.sandbox, SandboxManager)
    assert runner.sandbox.governor is not None

    # Execute safe command
    res = await runner.sandbox.run_command("echo 'test-ok'")
    assert res.exit_code == 0
    assert "test-ok" in res.stdout


@pytest.mark.asyncio
async def test_agent_memory_manager_delegates_to_canonical_engine(tmp_path):
    """Verify MemoryManager.remember() writes into canonical memory.engine.MemoryEngine."""
    db_file = str(tmp_path / "test_facts.db")
    wal_dir = str(tmp_path / "wal")
    working = WorkingMemoryTier(wal_dir=wal_dir)
    facts = FactStoreTier(db_path=db_file)
    vector = VectorMemoryTier()

    mock_canonical_engine = MagicMock(spec=MemoryEngine)
    mock_canonical_engine.remember.return_value = {"event_id": "mock-event-123"}

    mgr = MemoryManager(
        working=working,
        facts=facts,
        vector=vector,
        canonical_engine=mock_canonical_engine,
    )

    res = await mgr.remember(
        session_id="session-canonical-01",
        role="user",
        content="Remember that our production deployment must use mutual TLS.",
        namespace="tenant-canonical",
    )

    # Verify delegation took place
    assert res["canonical_synced"] is True
    assert mock_canonical_engine.remember.called
    call_kwargs = mock_canonical_engine.remember.call_args.kwargs
    assert call_kwargs["session_id"] == "session-canonical-01"
    assert call_kwargs["user_id"] == "tenant-canonical"
    assert "mutual TLS" in call_kwargs["text"]
