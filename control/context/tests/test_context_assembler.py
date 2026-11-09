"""Unit tests for Layer 9 Context Assembler (Tasks 9.1, Features 9.01 - 9.05)."""

import pytest
from control.context.assembly.context_assembler import (
    ContextAssembler,
    TokenBudgetConfig,
    AssemblyStrategy,
    ContextSource,
)


@pytest.fixture
def assembler():
    return ContextAssembler(
        config=TokenBudgetConfig(
            total_budget=4096,
            system_budget=500,
            memory_budget=800,
            knowledge_budget=1200,
            tools_budget=500,
            conversation_budget=1000,
            situational_budget=200,
        )
    )


def test_assemble_all_sources_represented(assembler):
    """Feature 9.01: Test context assembly from memory, knowledge, tools, and instructions."""
    system_instructions = "You are an enterprise AI assistant."
    situational_context = "Timestamp: 2026-11-10T02:00:00Z | Locale: en-US"
    memory_records = [
        {"key": "user_name", "value": "Alice", "category": "core_profile"},
        {"key": "project_pref", "value": "TypeScript strict mode", "category": "preference"},
    ]
    retrieved_knowledge = [
        {"doc_id": "arch_01", "content": "Central Intelligence uses a 12-layer architecture.", "score": 0.95},
        {"doc_id": "arch_02", "content": "Layer 9 handles context engineering.", "score": 0.88},
    ]
    active_tools = [
        {"name": "search_db", "description": "Query internal database", "parameters": {"properties": {"query": {}}}},
        {"name": "fetch_doc", "description": "Download document", "parameters": {"properties": {"id": {}}}},
    ]
    conversation_history = [
        {"role": "user", "content": "Hello! What is Central Intelligence?"},
        {"role": "assistant", "content": "Central Intelligence is an AI operating system."},
    ]

    result = assembler.assemble(
        system_instructions=system_instructions,
        situational_context=situational_context,
        memory_records=memory_records,
        retrieved_knowledge=retrieved_knowledge,
        active_tools=active_tools,
        conversation_history=conversation_history,
        user_id="user_alice",
        session_id="sess_123",
    )

    assert result.total_tokens <= 4096
    assert ContextSource.SYSTEM.value in result.sources_included
    assert ContextSource.MEMORY.value in result.sources_included
    assert ContextSource.KNOWLEDGE.value in result.sources_included
    assert ContextSource.TOOLS.value in result.sources_included
    assert ContextSource.CONVERSATION.value in result.sources_included
    assert ContextSource.SITUATIONAL.value in result.sources_included

    # Full prompt verification
    assert "You are an enterprise AI assistant." in result.full_prompt
    assert "user_name: Alice" in result.full_prompt
    assert "Layer 9 handles context engineering." in result.full_prompt
    assert "search_db" in result.full_prompt
    assert "What is Central Intelligence?" in result.full_prompt


def test_token_budget_per_source_enforced(assembler):
    """Feature 9.02: Test that source allocations prevent single-source starvation."""
    # Enormous knowledge chunks that exceed 1200 tokens
    huge_knowledge = [
        {"doc_id": f"doc_{i}", "content": "Central-Intelligence architecture specification. " * 50, "score": 0.9}
        for i in range(10)
    ]
    system_instructions = "System core prompt."
    tools = [{"name": "tool_exec", "description": "Execute action"}]

    result = assembler.assemble(
        system_instructions=system_instructions,
        retrieved_knowledge=huge_knowledge,
        active_tools=tools,
    )

    assert result.pruned is True
    # Knowledge must not starve system or tools
    assert result.token_counts["knowledge"] <= 1250
    assert result.token_counts["system"] > 0
    assert result.token_counts["tools"] > 0
    assert result.total_tokens <= assembler.config.total_budget


def test_multi_tier_prioritization_and_pruning(assembler):
    """Feature 9.03: When overall budget is constrained, knowledge is pruned before memory and system."""
    tight_assembler = ContextAssembler(
        config=TokenBudgetConfig(
            total_budget=200,
            system_budget=50,
            memory_budget=50,
            knowledge_budget=50,
            tools_budget=50,
            conversation_budget=50,
        )
    )

    system_instructions = "You are an executive agent."
    memory = [{"key": "role", "value": "CTO"}]
    tools = [{"name": "query_logs", "description": "Fetch audit logs"}]
    knowledge = [{"doc_id": "heavy_doc", "content": "Extensive corporate documentation " * 40}]

    result = tight_assembler.assemble(
        system_instructions=system_instructions,
        memory_records=memory,
        active_tools=tools,
        retrieved_knowledge=knowledge,
    )

    assert result.total_tokens <= tight_assembler.config.total_budget
    assert result.pruned is True
    # System and tools are highest priority, so they should remain
    assert "executive agent" in result.full_prompt
    assert "query_logs" in result.full_prompt


def test_10_turn_conversation_compaction_acceptance(assembler):
    """Feature 9.04 & Task 9.1 Acceptance:
    Assembled context for a 10-turn conversation fits within 4096 tokens with all sources represented.
    """
    ten_turns = [
        {"role": "user", "content": f"Turn {i}: Can you explain component {i} in detail? Provide full background."}
        if i % 2 == 1
        else {"role": "assistant", "content": f"Response {i}: Component {i} operates with multi-threaded resilience and handles events."}
        for i in range(1, 11)
    ]

    memory_records = [{"key": "user_status", "value": "active_developer"}]
    retrieved_knowledge = [{"doc_id": "ci_spec", "content": "Central Intelligence brain core components."}]
    tools = [{"name": "execute_code", "description": "Run Python script safely"}]

    result = assembler.assemble(
        system_instructions="You are Central Intelligence assistant.",
        memory_records=memory_records,
        retrieved_knowledge=retrieved_knowledge,
        active_tools=tools,
        conversation_history=ten_turns,
    )

    assert result.total_tokens <= 4096
    assert len(result.sources_included) == 5
    assert result.compacted is True
    assert "[Compacted Prior Conversation Summary]" in result.conversation_context
    # Most recent turns (turns 9 and 10) must be preserved in context
    assert "Component 10 operates" in result.full_prompt
    assert "execute_code" in result.full_prompt
    assert "active_developer" in result.full_prompt


def test_long_context_vs_retrieval_strategy_selection(assembler):
    """Feature 9.05: Dynamic strategy selector between long context and retrieval pruning."""
    # Under budget -> RETRIEVAL_PRUNED
    s1 = assembler.choose_strategy(raw_token_count=1500, target_model_window=128000)
    assert s1 == AssemblyStrategy.RETRIEVAL_PRUNED

    # High token count but under threshold with cost minimization off -> LONG_CONTEXT_PASS
    s2 = assembler.choose_strategy(
        raw_token_count=20000,
        target_model_window=128000,
        enforce_cost_minimization=False,
    )
    assert s2 == AssemblyStrategy.LONG_CONTEXT_PASS

    # Very large context near 80% model window -> COMPACTED_HYBRID
    s3 = assembler.choose_strategy(
        raw_token_count=110000,
        target_model_window=128000,
    )
    assert s3 == AssemblyStrategy.COMPACTED_HYBRID
