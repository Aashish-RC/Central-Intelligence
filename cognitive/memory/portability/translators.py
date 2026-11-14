"""Translators for ChatGPT, Claude, and CI Standard Memory Formats (Features 2.46, 2.50)."""

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from cognitive.memory.portability.models import (
    MemoryPortabilityFormat,
    StandardFactRecord,
    StandardMemoryExport,
    StandardTurnRecord,
)


class BaseTranslator(ABC):
    """Abstract base interface for format-specific memory translators."""

    @abstractmethod
    def parse(self, raw_data: Any, user_id: str) -> Tuple[List[StandardTurnRecord], List[StandardFactRecord]]:
        """Parse a raw source export payload into standardized turn and fact records."""

    @abstractmethod
    def format(self, turns: List[StandardTurnRecord], facts: List[StandardFactRecord], user_id: str) -> Dict[str, Any]:
        """Format standardized turn and fact records into the target assistant export schema."""


class StandardCITranslator(BaseTranslator):
    """Lossless CI Standard Memory format translator."""

    def parse(self, raw_data: Any, user_id: str) -> Tuple[List[StandardTurnRecord], List[StandardFactRecord]]:
        if isinstance(raw_data, str):
            raw_data = json.loads(raw_data)

        turns: List[StandardTurnRecord] = []
        facts: List[StandardFactRecord] = []

        for t in raw_data.get("turns", []):
            turns.append(StandardTurnRecord(**t))

        for f in raw_data.get("facts", []):
            facts.append(StandardFactRecord(**f))

        return turns, facts

    def format(self, turns: List[StandardTurnRecord], facts: List[StandardFactRecord], user_id: str) -> Dict[str, Any]:
        export = StandardMemoryExport(
            exported_at=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
            format=MemoryPortabilityFormat.CI_STANDARD,
            turns=turns,
            facts=facts,
        )
        return export.model_dump()


class ChatGPTTranslator(BaseTranslator):
    """Translator for OpenAI ChatGPT conversation data exports."""

    def parse(self, raw_data: Any, user_id: str) -> Tuple[List[StandardTurnRecord], List[StandardFactRecord]]:
        if isinstance(raw_data, str):
            raw_data = json.loads(raw_data)

        conversations = raw_data if isinstance(raw_data, list) else [raw_data]
        turns: List[StandardTurnRecord] = []
        facts: List[StandardFactRecord] = []

        for conv in conversations:
            session_id = conv.get("id") or conv.get("conversation_id") or "chatgpt_session"
            mapping = conv.get("mapping", {})

            for node_id, node in mapping.items():
                msg = node.get("message")
                if not msg:
                    continue

                author = msg.get("author", {})
                role = author.get("role", "user")
                if role not in ("user", "assistant", "system"):
                    continue

                content_obj = msg.get("content", {})
                parts = content_obj.get("parts", [])
                text_content = "".join([str(p) for p in parts if isinstance(p, (str, int, float))]).strip()

                if not text_content:
                    continue

                ts = None
                create_time = msg.get("create_time")
                if create_time:
                    try:
                        ts = datetime.fromtimestamp(create_time, timezone.utc).isoformat()
                    except Exception:
                        ts = None

                turns.append(
                    StandardTurnRecord(
                        id=msg.get("id", node_id),
                        role=role,
                        content=text_content,
                        timestamp=ts,
                        session_id=session_id,
                        metadata={"source": "chatgpt", "model": msg.get("metadata", {}).get("model_slug")},
                    )
                )

        return turns, facts

    def format(self, turns: List[StandardTurnRecord], facts: List[StandardFactRecord], user_id: str) -> Dict[str, Any]:
        mapping: Dict[str, Any] = {}
        for idx, turn in enumerate(turns):
            node_id = turn.id or f"node_{idx}"
            mapping[node_id] = {
                "id": node_id,
                "message": {
                    "id": node_id,
                    "author": {"role": turn.role},
                    "content": {"content_type": "text", "parts": [turn.content]},
                },
                "parent": f"node_{idx - 1}" if idx > 0 else None,
                "children": [f"node_{idx + 1}"] if idx < len(turns) - 1 else [],
            }

        return {
            "title": f"Central-Intelligence Export for {user_id}",
            "create_time": datetime.now(timezone.utc).timestamp(),
            "mapping": mapping,
            "format": "chatgpt_export",
        }


class ClaudeTranslator(BaseTranslator):
    """Translator for Anthropic Claude conversation data exports."""

    def parse(self, raw_data: Any, user_id: str) -> Tuple[List[StandardTurnRecord], List[StandardFactRecord]]:
        if isinstance(raw_data, str):
            raw_data = json.loads(raw_data)

        conversations = raw_data if isinstance(raw_data, list) else [raw_data]
        turns: List[StandardTurnRecord] = []
        facts: List[StandardFactRecord] = []

        for conv in conversations:
            session_id = conv.get("uuid") or conv.get("id") or "claude_session"
            messages = conv.get("chat_messages", [])

            for msg in messages:
                sender = msg.get("sender", "human")
                role = "user" if sender == "human" else "assistant"
                content = msg.get("text", "").strip()

                if not content:
                    continue

                turns.append(
                    StandardTurnRecord(
                        id=msg.get("uuid"),
                        role=role,
                        content=content,
                        timestamp=msg.get("created_at"),
                        session_id=session_id,
                        metadata={"source": "claude"},
                    )
                )

        return turns, facts

    def format(self, turns: List[StandardTurnRecord], facts: List[StandardFactRecord], user_id: str) -> Dict[str, Any]:
        chat_messages = []
        for turn in turns:
            sender = "human" if turn.role == "user" else "assistant"
            chat_messages.append({
                "uuid": turn.id or f"msg_{len(chat_messages)}",
                "text": turn.content,
                "sender": sender,
                "created_at": turn.timestamp or datetime.now(timezone.utc).isoformat(),
            })

        return {
            "uuid": f"conv_{user_id}",
            "name": f"CI Memory Export ({user_id})",
            "chat_messages": chat_messages,
            "format": "claude_export",
        }
