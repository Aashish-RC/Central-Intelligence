"""Stitch 4: Dynamic Context Synthesizer enforcing strict token budgets."""

from typing import List, Optional
import tiktoken

from memory.core.models import ContextPackage, Turn, FactItem, MemoryRecord
from memory.config import MemoryConfig


class ContextSynthesizer:
    """Merges Tier 1 working turns, Tier 2 core facts, and Tier 3 semantic memories
    into a concentrated, token-budgeted prompt injection (< 500 tokens).
    """

    def __init__(self, config: Optional[MemoryConfig] = None):
        if config is None:
            from memory.config import default_config
            config = default_config
        self._config = config
        self._max_tokens = config.max_context_tokens

        try:
            self._encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._encoder = None

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if self._encoder is not None:
            try:
                return len(self._encoder.encode(text))
            except Exception:
                pass
        # Fallback approximation: 1 token ~= 4 chars or 0.75 words
        return max(1, len(text.split()) * 4 // 3)

    def synthesize(
        self,
        user_id: str,
        session_id: Optional[str],
        working_turns: List[Turn],
        core_facts: List[FactItem],
        archival_memories: List[MemoryRecord],
        tenant_id: str = "default",
    ) -> ContextPackage:
        """Constructs an optimized, token-bounded context string."""
        # Section 1: Active Core Facts (Tier 2) - Priority 1
        fact_lines = []
        for f in core_facts:
            fact_lines.append(f"- {f.key}: {f.value} [{f.category.value}]")
        facts_text = "\n".join(fact_lines)

        # Section 2: Relevant Archival Memories (Tier 3) - Priority 2
        archival_lines = []
        for m in archival_memories:
            archival_lines.append(f"- {m.text.strip()}")
        archival_text = "\n".join(archival_lines)

        # Section 3: Recent Working Window (Tier 1) - Priority 3
        turn_lines = []
        for t in working_turns:
            turn_lines.append(f"{t.role.value}: {t.content.strip()}")

        # Build candidate prompt and prune turns/memories if exceeding budget
        while True:
            parts = []
            parts.append("<agent_memory_context>")

            if facts_text:
                parts.append("### Active Profile & Facts")
                parts.append(facts_text)

            if archival_text:
                parts.append("### Retrieved Archival Context")
                parts.append(archival_text)

            if turn_lines:
                parts.append("### Working Session Context")
                parts.append("\n".join(turn_lines))

            parts.append("</agent_memory_context>")
            candidate_prompt = "\n".join(parts)
            token_count = self.count_tokens(candidate_prompt)

            if token_count <= self._max_tokens or (not turn_lines and not archival_lines):
                break

            # Trim working turns first (oldest first)
            if turn_lines:
                turn_lines.pop(0)
            # Then trim archival memories
            elif archival_lines:
                archival_lines.pop()
                archival_text = "\n".join(archival_lines)

        final_token_count = self.count_tokens(candidate_prompt)

        return ContextPackage(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            working_memory=working_turns,
            core_facts=core_facts,
            archival_matches=archival_memories,
            formatted_prompt=candidate_prompt,
            token_count=final_token_count,
            metadata={"max_budget": self._max_tokens},
        )
