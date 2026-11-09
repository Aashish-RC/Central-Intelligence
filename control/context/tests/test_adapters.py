"""Unit tests for Per-Model Context Format Adapters (Task 9.6, Feature 9.15)."""

import pytest
from control.context.assembly.context_assembler import ContextAssembler
from control.context.adapters.anthropic_adapter import AnthropicContextAdapter
from control.context.adapters.openai_adapter import OpenAIContextAdapter
from control.context.adapters.gemini_adapter import GeminiContextAdapter
from control.context.adapters.ollama_adapter import OllamaContextAdapter


@pytest.fixture
def sample_assembled_context():
    assembler = ContextAssembler()
    return assembler.assemble(
        system_instructions="You are Central Intelligence assistant.",
        memory_records=[{"key": "user_id", "value": "alice_123"}],
        retrieved_knowledge=[{"doc_id": "doc1", "content": "Knowledge content 1."}],
        active_tools=[{"name": "fetch_metric", "description": "Fetch metrics"}],
        conversation_history=[
            {"role": "user", "content": "What are current server metrics?"},
            {"role": "assistant", "content": "Server CPU is 42%."},
        ],
    )


def test_adapters_format_conformance_acceptance(sample_assembled_context):
    """Task 9.6 Acceptance:
    Same assembled context produces correctly formatted requests for all 4 providers.
    """
    conversation = [
        {"role": "user", "content": "What are current server metrics?"},
        {"role": "assistant", "content": "Server CPU is 42%."},
        {"role": "user", "content": "Can you generate a summary report?"},
    ]

    # 1. Anthropic Format
    anthropic_req = AnthropicContextAdapter.format(sample_assembled_context, conversation)
    assert "system" in anthropic_req
    assert "messages" in anthropic_req
    assert isinstance(anthropic_req["system"], str)
    assert "You are Central Intelligence assistant." in anthropic_req["system"]
    assert "fetch_metric" in anthropic_req["system"]
    assert len(anthropic_req["messages"]) == 3
    assert anthropic_req["messages"][0]["role"] == "user"
    assert anthropic_req["messages"][1]["role"] == "assistant"
    assert anthropic_req["messages"][2]["role"] == "user"

    # 2. OpenAI Format
    openai_req = OpenAIContextAdapter.format(sample_assembled_context, conversation)
    assert "messages" in openai_req
    # System message must be index 0
    assert openai_req["messages"][0]["role"] == "system"
    assert "You are Central Intelligence assistant." in openai_req["messages"][0]["content"]
    assert "fetch_metric" in openai_req["messages"][0]["content"]
    assert len(openai_req["messages"]) == 4  # system + 3 conversation turns
    assert openai_req["messages"][1]["role"] == "user"

    # OpenAI with developer role (for o1/o3-series)
    openai_dev_req = OpenAIContextAdapter.format(
        sample_assembled_context, conversation, use_developer_role=True
    )
    assert openai_dev_req["messages"][0]["role"] == "developer"

    # 3. Gemini Format
    gemini_req = GeminiContextAdapter.format(sample_assembled_context, conversation)
    assert "systemInstruction" in gemini_req
    assert "parts" in gemini_req["systemInstruction"]
    assert "You are Central Intelligence assistant." in gemini_req["systemInstruction"]["parts"][0]["text"]
    assert "contents" in gemini_req
    assert len(gemini_req["contents"]) == 3
    assert gemini_req["contents"][0]["role"] == "user"
    assert gemini_req["contents"][1]["role"] == "model"
    assert gemini_req["contents"][2]["role"] == "user"
    assert gemini_req["contents"][2]["parts"][0]["text"] == "Can you generate a summary report?"

    # 4. Ollama Format
    ollama_req = OllamaContextAdapter.format(sample_assembled_context, conversation)
    assert "system" in ollama_req
    assert "messages" in ollama_req
    assert "You are Central Intelligence assistant." in ollama_req["system"]
    assert len(ollama_req["messages"]) == 3
    assert ollama_req["messages"][0]["role"] == "user"
    assert ollama_req["messages"][1]["role"] == "assistant"
