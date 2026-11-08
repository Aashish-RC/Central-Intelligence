"""Memory Cognition: Automated Fact Extraction (Mem0) & 3-Tier Paging (Letta)."""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExtractedFact(BaseModel):
    entity_key: str
    fact_text: str
    category: str = "general"
    confidence: float = 0.9


class MemoryContextBlock(BaseModel):
    """Synthesized 3-tier context package formatted for injection into LLM prompts."""

    working_context: List[Dict[str, Any]] = Field(default_factory=list)
    core_facts: List[Dict[str, Any]] = Field(default_factory=list)
    semantic_matches: List[Dict[str, Any]] = Field(default_factory=list)

    def to_system_prompt_section(self) -> str:
        """Render markdown context block for system prompt."""
        sections = []

        if self.core_facts:
            facts_str = "\n".join(f"- [{f['category'].upper()}] {f['entity_key']}: {f['fact_text']}" for f in self.core_facts)
            sections.append(f"### [Core Memory & Rules]\n{facts_str}")

        if self.semantic_matches:
            kb_str = "\n".join(f"- (relevance {m.get('score', 0):.2f}): {m['text']}" for m in self.semantic_matches)
            sections.append(f"### [Retrieved Knowledge Base]\n{kb_str}")

        return "\n\n".join(sections)


class MemoryCognition:
    """Cognitive Controller performing fact extraction and memory paging."""

    # Heuristic extraction patterns for rule/preference facts
    FACT_PATTERNS = [
        (r"(?:my name is|i am|call me)\s+([A-Za-z0-9_-]+)", "user_name", "identity"),
        (r"(?:i prefer|i like|always use)\s+([^\.]+)", "preference", "user_preference"),
        (r"(?:never use|do not use|avoid)\s+([^\.]+)", "constraint", "constraint"),
        (r"(?:rule|policy):\s*([^\.]+)", "compliance_rule", "compliance"),
    ]

    @classmethod
    def extract_facts(cls, text: str) -> List[ExtractedFact]:
        """Extract structured facts from user interaction text."""
        facts: List[ExtractedFact] = []

        for pattern, entity_key, category in cls.FACT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted_val = match.group(1).strip()
                facts.append(
                    ExtractedFact(
                        entity_key=entity_key,
                        fact_text=extracted_val,
                        category=category,
                        confidence=0.95
                    )
                )

        return facts

    @classmethod
    def synthesize_context(
        cls,
        recent_turns: List[Dict[str, Any]],
        facts: List[Dict[str, Any]],
        semantic_matches: List[Dict[str, Any]],
    ) -> MemoryContextBlock:
        """Assemble a unified 3-tier memory context block."""
        return MemoryContextBlock(
            working_context=recent_turns,
            core_facts=facts,
            semantic_matches=semantic_matches,
        )
