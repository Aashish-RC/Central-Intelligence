"""Live integration tests for LibreChatAdapter Layer 4 gateway bridge (Milestone 4 - Task 4.3)."""

import os
import pytest
from control.safety.production_guard import ProductionSafetyError
from surface.interaction.web.librechat_adapter import (
    ChatMessage,
    LibreChatAdapter,
)


@pytest.fixture
def live_gateway_url():
    url = os.getenv("REASONING_GATEWAY_URL")
    if not url:
        pytest.skip("Requires REASONING_GATEWAY_URL env var")
    return url.rstrip("/")


@pytest.fixture
def live_adapter(live_gateway_url, monkeypatch):
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    api_key = os.getenv("REASONING_GATEWAY_API_KEY", "test_key")
    return LibreChatAdapter(gateway_url=live_gateway_url, api_key=api_key)


@pytest.mark.live
def test_send_message_returns_real_llm_response(live_adapter):
    """send_message() routes to Layer 4 gateway and returns assistant response with LLM completion."""
    conv = live_adapter.create_conversation(
        title="Math Prompt",
        provider="openai",
        model="gpt-4o",
    )
    reply1 = live_adapter.send_message(conv.conversation_id, "What is 2+2? Answer with just the number.")
    assert reply1.role == "assistant"
    assert any(char.isdigit() for char in reply1.content)

    conv2 = live_adapter.create_conversation(
        title="Math Prompt 2",
        provider="openai",
        model="gpt-4o",
    )
    reply2 = live_adapter.send_message(conv2.conversation_id, "What is 3+3? Answer with just the number.")
    assert reply2.role == "assistant"
    assert reply1.content != reply2.content or "6" in reply2.content


@pytest.mark.live
def test_conversation_history_preserved(live_adapter):
    """Conversation history retains both user queries and assistant responses (4 total for 2 turns)."""
    conv = live_adapter.create_conversation(
        title="Multi-turn Conversation",
        provider="openai",
        model="gpt-4o",
    )
    live_adapter.send_message(conv.conversation_id, "Hello, who are you?")
    live_adapter.send_message(conv.conversation_id, "What is the capital of France?")

    fetched = live_adapter.get_conversation(conv.conversation_id)
    assert fetched is not None
    assert len(fetched.messages) == 4
    roles = [m.role for m in fetched.messages]
    assert roles == ["user", "assistant", "user", "assistant"]


@pytest.mark.live
def test_gateway_down_fails_closed(monkeypatch):
    """When the reasoning gateway is unreachable and ADAPTER_MODE=live, send_message() raises ProductionSafetyError."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    adapter = LibreChatAdapter(
        gateway_url="http://127.0.0.1:59998",
        api_key="test_key",
        _defer_prod_check=True,
    )
    adapter.adapter_mode = "live"

    conv = adapter.create_conversation(title="Test Fail Closed")
    with pytest.raises(ProductionSafetyError):
        adapter.send_message(conv.conversation_id, "Hello world")
