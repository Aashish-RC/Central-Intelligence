"""Prefix Cache Optimizer (Layer 9: Context Engineering, Feature 9.14).

Aligns static, invariant context blocks (system instructions, tool declarations,
fixed schemas) at the prompt's prefix to maximize KV-cache reuse on providers
like Anthropic (Prompt Caching) and OpenAI (Automatic Prefix Caching).
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple


class SectionStability(IntEnum):
    """Stability tier of a context block (lower numbers placed first for cache affinity)."""
    STATIC_SYSTEM = 1       # Base system prompt, immutable rules
    STATIC_TOOLS = 2        # Active tool function definitions and schemas
    STATIC_GUIDELINES = 3   # Org/app static guidelines
    SEMI_STATIC_KNOWLEDGE = 4 # Retrieved reference material (cached across queries in session)
    DYNAMIC_MEMORY = 5      # Ephemeral user facts / recent memory
    DYNAMIC_CONVERSATION = 6 # Active user turns and recent assistant answers


@dataclass
class CacheableSection:
    """Individual section of context with stability classification."""
    name: str
    content: str
    stability: SectionStability
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizedContextResult:
    """Result of prefix cache reordering."""
    optimized_prompt: str
    ordered_sections: List[CacheableSection]
    static_prefix_tokens: int
    dynamic_suffix_tokens: int
    cacheable_ratio: float  # static_prefix_tokens / total_tokens


class PrefixCacheOptimizer:
    """Reorders prompt context sections to maximize provider KV-cache hits (9.14)."""

    @staticmethod
    def optimize_sections(sections: List[CacheableSection]) -> List[CacheableSection]:
        """Orders sections strictly ascending by stability tier."""
        return sorted(sections, key=lambda s: s.stability.value)

    @classmethod
    def assemble_optimized(
        cls,
        sections: List[CacheableSection],
        delimiter: str = "\n\n",
    ) -> OptimizedContextResult:
        """Sorts sections by stability and renders final prefix-aligned prompt string."""
        ordered = cls.optimize_sections(sections)
        blocks = [s.content.strip() for s in ordered if s.content.strip()]
        full_prompt = delimiter.join(blocks)

        static_tokens = sum(
            s.token_count
            for s in ordered
            if s.stability <= SectionStability.STATIC_GUIDELINES
        )
        dynamic_tokens = sum(
            s.token_count
            for s in ordered
            if s.stability > SectionStability.STATIC_GUIDELINES
        )
        total = static_tokens + dynamic_tokens
        ratio = (static_tokens / total) if total > 0 else 0.0

        return OptimizedContextResult(
            optimized_prompt=full_prompt,
            ordered_sections=ordered,
            static_prefix_tokens=static_tokens,
            dynamic_suffix_tokens=dynamic_tokens,
            cacheable_ratio=ratio,
        )

    @staticmethod
    def compute_prefix_overlap_ratio(prompt_a: str, prompt_b: str) -> float:
        """Computes character/token prefix overlap ratio between two prompts."""
        if not prompt_a or not prompt_b:
            return 0.0
        # Common prefix length
        common_len = 0
        min_len = min(len(prompt_a), len(prompt_b))
        for i in range(min_len):
            if prompt_a[i] == prompt_b[i]:
                common_len += 1
            else:
                break
        return common_len / max(len(prompt_a), len(prompt_b))
