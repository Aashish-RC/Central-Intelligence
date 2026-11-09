"""Google Gemini Context Format Adapter (Layer 9: Context Engineering, Feature 9.15)."""

from typing import Any, Dict, List, Optional
from control.context.assembly.context_assembler import AssembledContext


class GeminiContextAdapter:
    """Formats unified assembled context into Google Gemini Generative API schema."""

    @staticmethod
    def format(
        assembled: AssembledContext,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Translates assembled context into Gemini format:

        - 'systemInstruction' with {'parts': [{'text': ...}]}
        - 'contents' array with alternating 'user' and 'model' roles and {'parts': [{'text': ...}]}
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

        system_instruction = {
            "parts": [{"text": "\n\n".join(system_parts)}]
        }

        contents = []
        if conversation_history:
            for turn in conversation_history:
                role = "model" if turn.get("role") in ("assistant", "model") else "user"
                contents.append({
                    "role": role,
                    "parts": [{"text": turn.get("content", "")}],
                })
        elif assembled.conversation_context:
            contents.append({
                "role": "user",
                "parts": [{"text": assembled.conversation_context}],
            })
        else:
            contents.append({
                "role": "user",
                "parts": [{"text": "Please proceed."}],
            })

        return {
            "systemInstruction": system_instruction,
            "contents": contents,
        }
