"""LibreChat Web Chat Adapter (L18 Interaction - Task 18.1).

Provides multi-provider chat session management and unified conversation
rendering across OpenAI, Anthropic, Google Gemini, Ollama, and custom endpoints.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    require_live_adapter,
)

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

    def __init__(
        self,
        gateway_url: str = "http://localhost:8787",
        api_key: Optional[str] = None,
        _defer_prod_check: bool = False,
    ) -> None:
        self.gateway_url = (gateway_url or os.getenv("REASONING_GATEWAY_URL", "http://localhost:8787")).rstrip("/")
        self.api_key = api_key or os.getenv("REASONING_GATEWAY_API_KEY")
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("librechat")
        )
        self._conversations: Dict[str, ChatConversation] = {}
        self._providers = {
            "openai": ["gpt-4o", "gpt-4o-mini"],
            "anthropic": ["claude-3-7-sonnet", "claude-3-5-haiku"],
            "google": ["gemini-1.5-pro", "gemini-1.5-flash"],
            "ollama": ["llama3.2", "qwen2.5-coder"],
        }
        self._http_client: Optional[Any] = None
        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            self._ensure_live_backend()

    def _get_client(self) -> Any:
        if self._http_client is None:
            import httpx
            self._http_client = httpx.Client(timeout=120.0)
        return self._http_client

    def _ensure_live_backend(self) -> None:
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            return
        try:
            import httpx
            resp = httpx.get(f"{self.gateway_url}/healthz", timeout=5.0)
            if resp.status_code not in (200, 204):
                fail_closed_in_production(
                    "librechat",
                    f"Reasoning gateway returned HTTP {resp.status_code}",
                )
            self._http_client = httpx.Client(timeout=120.0)
        except ProductionSafetyError:
            raise
        except Exception as exc:
            fail_closed_in_production(
                "librechat",
                f"Reasoning gateway at {self.gateway_url} unreachable: {exc}",
                cause=exc,
            )

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
        user_msg = ChatMessage(
            message_id=msg_id,
            role=role,
            content=content,
            provider=provider,
            model=model,
        )
        conv.messages.append(user_msg)

        # Hermetic path — preserve existing mock-reply behavior
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            return user_msg

        # Live path — call the Layer 4 reasoning gateway
        if role != "user":
            return user_msg

        try:
            client = self._http_client or self._get_client()
            payload = {
                "model": model,
                "messages": [
                    {"role": m.role, "content": m.content} for m in conv.messages
                ],
                "stream": False,
            }
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            resp = client.post(
                f"{self.gateway_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=120.0,
            )
            if resp.status_code != 200:
                fail_closed_in_production(
                    "librechat",
                    f"Reasoning gateway returned HTTP {resp.status_code}: {resp.text}",
                )
            data = resp.json()
            assistant_content = data["choices"][0]["message"]["content"]
            assistant_msg = ChatMessage(
                message_id=f"msg_{uuid.uuid4().hex[:10]}",
                role="assistant",
                content=assistant_content,
                provider=provider,
                model=model,
            )
            conv.messages.append(assistant_msg)
            return assistant_msg
        except ProductionSafetyError:
            raise
        except Exception as exc:
            fail_closed_in_production(
                "librechat",
                f"Reasoning gateway call failed: {exc}",
                cause=exc,
            )

    def get_conversation(self, conversation_id: str) -> Optional[ChatConversation]:
        return self._conversations.get(conversation_id)
