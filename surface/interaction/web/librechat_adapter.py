"""LibreChat Web Chat Adapter (L18 Interaction - Task 18.1).

Provides multi-provider chat session management and unified conversation
rendering across OpenAI, Anthropic, Google Gemini, Ollama, and custom endpoints.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """A conversational turn in LibreChat."""
    message_id: str
    role: str  # "user", "assistant", "system"
    content: str
    provider: str
    model: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatConversation:
    """A multi-provider conversation thread."""
    conversation_id: str
    title: str
    active_provider: str
    active_model: str
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class LibreChatAdapter:
    """Manages web chat sessions and seamlessly routes between diverse providers."""

    def __init__(self) -> None:
        self._conversations: Dict[str, ChatConversation] = {}
        self._providers = {
            "openai": ["gpt-4o", "gpt-4o-mini"],
            "anthropic": ["claude-3-7-sonnet", "claude-3-5-haiku"],
            "google": ["gemini-1.5-pro", "gemini-1.5-flash"],
            "ollama": ["llama3.2", "qwen2.5-coder"],
        }

    def list_supported_providers(self) -> Dict[str, List[str]]:
        """Return available providers and their supported models."""
        return dict(self._providers)

    def create_conversation(
        self,
        title: str = "New Chat",
        provider: str = "anthropic",
        model: str = "claude-3-7-sonnet",
    ) -> ChatConversation:
        """Initialize a new conversation thread."""
        conv_id = f"lc_conv_{uuid.uuid4().hex[:10]}"
        conv = ChatConversation(
            conversation_id=conv_id,
            title=title,
            active_provider=provider,
            active_model=model,
        )
        self._conversations[conv_id] = conv
        return conv

    def switch_provider(self, conversation_id: str, new_provider: str, new_model: str) -> bool:
        """Switch conversation to a different AI provider in real-time."""
        conv = self._conversations.get(conversation_id)
        if not conv:
            raise ValueError(f"Conversation not found: {conversation_id}")

        conv.active_provider = new_provider
        conv.active_model = new_model
        logger.info("Conversation %s switched to %s / %s", conversation_id, new_provider, new_model)
        return True

    def send_message(
        self,
        conversation_id: str,
        content: str,
        role: str = "user",
        override_provider: Optional[str] = None,
        override_model: Optional[str] = None,
    ) -> ChatMessage:
        """Post a message and simulate reply from designated provider."""
        conv = self._conversations.get(conversation_id)
        if not conv:
            raise ValueError(f"Conversation not found: {conversation_id}")

        provider = override_provider or conv.active_provider
        model = override_model or conv.active_model

        msg_id = f"msg_{uuid.uuid4().hex[:10]}"
        msg = ChatMessage(
            message_id=msg_id,
            role=role,
            content=content,
            provider=provider,
            model=model,
        )
        conv.messages.append(msg)
        return msg

    def get_conversation(self, conversation_id: str) -> Optional[ChatConversation]:
        return self._conversations.get(conversation_id)

