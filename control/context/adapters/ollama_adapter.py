"""Ollama Local Runtime Context Format Adapter (Layer 9: Context Engineering, Feature 9.15)."""

from typing import Any, Dict, List, Optional
from control.context.assembly.context_assembler import AssembledContext


class OllamaContextAdapter:
    """Formats unified assembled context into native Ollama /api/chat schema."""

    @staticmethod
    def format(
        assembled: AssembledContext,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Translates assembled context into Ollama format:

        - 'system' top-level prompt parameter
        - 'messages' array with 'user' and 'assistant' roles
        """
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

        messages = []
        if conversation_history:
            for turn in conversation_history:
                role = "assistant" if turn.get("role") in ("assistant", "model") else "user"
                messages.append({"role": role, "content": turn.get("content", "")})
        elif assembled.conversation_context:
            messages.append({"role": "user", "content": assembled.conversation_context})
        else:
            messages.append({"role": "user", "content": "Please proceed."})

        return {
            "system": system_text,
            "messages": messages,
        }
