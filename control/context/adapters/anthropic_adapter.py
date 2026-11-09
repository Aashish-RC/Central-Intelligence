"""Anthropic Context Format Adapter (Layer 9: Context Engineering, Feature 9.15)."""

from typing import Any, Dict, List, Optional
from control.context.assembly.context_assembler import AssembledContext


class AnthropicContextAdapter:
    """Formats unified assembled context into native Anthropic Claude request schema."""

    @staticmethod
    def format(
        assembled: AssembledContext,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Translates assembled context into Anthropic format:

        - 'system' top-level parameter (outside messages array)
        - 'messages' array containing alternating 'user' and 'assistant' roles
        """
        # System instructions and static context go to top-level system parameter
        system_parts = []
        if assembled.system_prompt:
            system_parts.append(assembled.system_prompt)
        if assembled.tools_context:
            system_parts.append(f"<active_tools>\n{assembled.tools_context}\n</active_tools>")
        if assembled.knowledge_context:
            system_parts.append(f"<retrieved_knowledge>\n{assembled.knowledge_context}\n</retrieved_knowledge>")
        if assembled.memory_context:
            system_parts.append(f"<memory_context>\n{assembled.memory_context}\n</memory_context>")

        system_text = "\n\n".join(system_parts)

        # Messages array
        messages = []
        if conversation_history:
            for turn in conversation_history:
                role = "assistant" if turn.get("role") in ("assistant", "model") else "user"
                messages.append({"role": role, "content": turn.get("content", "")})
        elif assembled.conversation_context:
            messages.append({"role": "user", "content": assembled.conversation_context})
        else:
            messages.append({"role": "user", "content": "Please proceed."})

        # Anthropic requires the first message to be role 'user'
        if messages and messages[0]["role"] != "user":
            messages.insert(0, {"role": "user", "content": "Context initialized."})

        return {
            "system": system_text,
            "messages": messages,
        }
