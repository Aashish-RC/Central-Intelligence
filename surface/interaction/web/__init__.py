"""Web interaction subsystem via LibreChat (L18 Interaction)."""

from .librechat_adapter import (
    LibreChatAdapter,
    ChatMessage,
    ChatConversation,
)

__all__ = [
    "LibreChatAdapter",
    "ChatMessage",
    "ChatConversation",
]
