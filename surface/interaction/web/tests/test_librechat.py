"""Unit tests for LibreChatAdapter (Task 18.1)."""

import pytest
from surface.interaction.web.librechat_adapter import (
    LibreChatAdapter,
    ChatConversation,
)


@pytest.fixture
def librechat():
    return LibreChatAdapter()


def test_chat_with_multiple_providers_in_one_ui(librechat: LibreChatAdapter):
    """Acceptance test: Can chat with multiple providers in one UI."""
    # 1. Start chat with Anthropic Claude
    conv = librechat.create_conversation(
        title="Cross-Provider Architecture",
        provider="anthropic",
        model="claude-3-7-sonnet",
    )
    assert conv.active_provider == "anthropic"

    # User message & Anthropic response
    librechat.send_message(conv.conversation_id, "Explain CRDTs", role="user")
    librechat.send_message(conv.conversation_id, "CRDTs ensure strong eventual consistency.", role="assistant")

    # 2. Switch provider mid-thread to OpenAI GPT-4o
    librechat.switch_provider(conv.conversation_id, new_provider="openai", new_model="gpt-4o")
    assert conv.active_provider == "openai"

    # User follow-up & OpenAI response
    librechat.send_message(conv.conversation_id, "Compare with Operational Transformation", role="user")
    librechat.send_message(conv.conversation_id, "OT requires a central sequencer unlike CRDTs.", role="assistant")

    # 3. Switch to local Ollama
    librechat.switch_provider(conv.conversation_id, new_provider="ollama", new_model="llama3.2")
    librechat.send_message(conv.conversation_id, "Provide Python code snippet", role="user")
    librechat.send_message(conv.conversation_id, "class LWWRegister: ...", role="assistant")

    # Verify conversation history contains responses from all 3 providers
    saved_conv = librechat.get_conversation(conv.conversation_id)
    assert saved_conv is not None
    assert len(saved_conv.messages) == 6

    providers_used = {m.provider for m in saved_conv.messages if m.role == "assistant"}
    assert providers_used == {"anthropic", "openai", "ollama"}
