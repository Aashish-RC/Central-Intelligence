"""Context Assembler Module (Layer 9: Context Engineering)

Implements:
- 9.01: Context assembly across memory (L2), knowledge (L3), tools (L5), and instructions
- 9.02: Granular token budgets per context source with overflow safeguards
- 9.03: Strict multi-tier prioritization and pruning hierarchy
- 9.04: Conversation compaction and history rolling summarization
- 9.05: Dynamic strategy selector (Long Context vs Retrieval-Augmented Context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False

try:
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.core.schema import Document
    _LLAMA_INDEX_AVAILABLE = True
except ImportError:
    _LLAMA_INDEX_AVAILABLE = False

logger = logging.getLogger("control.context.assembly")


class ContextSource(str, Enum):
    SYSTEM = "system"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    TOOLS = "tools"
    CONVERSATION = "conversation"
    SITUATIONAL = "situational"


class AssemblyStrategy(str, Enum):
    RETRIEVAL_PRUNED = "retrieval_pruned"
    LONG_CONTEXT_PASS = "long_context_pass"
    COMPACTED_HYBRID = "compacted_hybrid"


@dataclass
class TokenBudgetConfig:
    """Configurable token allocations per source category."""
    total_budget: int = 4096
    system_budget: int = 600
    memory_budget: int = 800
    knowledge_budget: int = 1200
    tools_budget: int = 500
    conversation_budget: int = 1000
    situational_budget: int = 200
    # Enable dynamic budget borrowing from unused allocations
    allow_budget_reallocation: bool = True
    # Threshold in tokens to switch from retrieval to long context
    long_context_threshold: int = 32000
    # Threshold in turn count to trigger conversation compaction
    max_history_turns_before_compaction: int = 6


@dataclass
class AssembledContext:
    """Standardized output structure for assembled context."""
    system_prompt: str
    memory_context: str
    knowledge_context: str
    tools_context: str
    conversation_context: str
    full_prompt: str
    token_counts: Dict[str, int] = field(default_factory=dict)
    total_tokens: int = 0
    sources_included: List[str] = field(default_factory=list)
    pruned: bool = False
    compacted: bool = False
    strategy_used: AssemblyStrategy = AssemblyStrategy.RETRIEVAL_PRUNED
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextAssembler:
    """Assembles and compacts context from L2, L3, L5 and system prompts."""

    def __init__(
        self,
        config: Optional[TokenBudgetConfig] = None,
        model_name: str = "gpt-4",
    ):
        self.config = config or TokenBudgetConfig()
        self.model_name = model_name
        self._encoder = None
        if _TIKTOKEN_AVAILABLE:
            try:
                self._encoder = tiktoken.encoding_for_model(model_name)
            except Exception:
                try:
                    self._encoder = tiktoken.get_encoding("cl100k_base")
                except Exception:
                    self._encoder = None

    def count_tokens(self, text: Optional[str]) -> int:
        """Accurately calculates token length with robust fallback."""
        if not text:
            return 0
        if self._encoder is not None:
            try:
                return len(self._encoder.encode(text))
            except Exception:
                pass
        # Fallback estimation: ~4 chars per token in English text
        return max(1, len(text) // 4)

    def choose_strategy(
        self,
        raw_token_count: int,
        target_model_window: int = 128000,
        enforce_cost_minimization: bool = True,
    ) -> AssemblyStrategy:
        """Feature 9.05: Decision logic for Long Context vs Retrieval-Augmented Compaction.

        Determines whether the model window can comfortably swallow the entire context
        without degradation ("needle in a haystack" penalty / high token cost) or if
        targeted retrieval + compaction is optimal.
        """
        if raw_token_count <= self.config.total_budget:
            return AssemblyStrategy.RETRIEVAL_PRUNED

        if raw_token_count > target_model_window * 0.8:
            # Context is dangerously close to or exceeds the model context window
            return AssemblyStrategy.COMPACTED_HYBRID

        if not enforce_cost_minimization and raw_token_count < self.config.long_context_threshold:
            return AssemblyStrategy.LONG_CONTEXT_PASS

        return AssemblyStrategy.COMPACTED_HYBRID

    def compact_conversation(
        self,
        history: List[Dict[str, str]],
        max_tokens: int,
        keep_recent_turns: int = 4,
        max_turns: Optional[int] = None,
    ) -> Tuple[List[Dict[str, str]], bool]:
        """Feature 9.04: Compact older conversation turns into a summarized synthesis block.

        Preserves the most recent N turns intact for local coherence while compacting
        older turns into bullet-point abstracts.
        """
        if not history:
            return [], False

        max_turns = (
            max_turns
            if max_turns is not None
            else self.config.max_history_turns_before_compaction
        )
        total_tokens = sum(
            self.count_tokens(f"{t.get('role')}: {t.get('content')}") for t in history
        )
        if total_tokens <= max_tokens and len(history) <= max_turns:
            return history, False

        # Split into older turns to compact and recent turns to preserve
        effective_keep = min(keep_recent_turns, len(history))
        older_turns = history[:-effective_keep]
        recent_turns = history[-effective_keep:]

        # Compact older turns
        summary_bullets = []
        for turn in older_turns:
            role = turn.get("role", "unknown").capitalize()
            content = turn.get("content", "").strip()
            # Truncate content to essential gist
            first_sentence = content.split("\n")[0].split(". ")[0]
            if len(first_sentence) > 120:
                first_sentence = first_sentence[:117] + "..."
            summary_bullets.append(f"- {role}: {first_sentence}")

        compacted_turn = {
            "role": "system",
            "content": "[Compacted Prior Conversation Summary]:\n" + "\n".join(summary_bullets),
            "is_compacted": True,
        }

        compacted_history = [compacted_turn] + recent_turns

        # Check if further pruning of older recent turns is necessary
        while len(compacted_history) > 2:
            current_tokens = sum(
                self.count_tokens(f"{t.get('role')}: {t.get('content')}") for t in compacted_history
            )
            if current_tokens <= max_tokens:
                break
            # Pop oldest uncompacted recent turn
            compacted_history.pop(1)

        return compacted_history, True

    def _format_memory(self, memory_records: List[Union[Dict[str, Any], str]]) -> str:
        """Format L2 memory facts and archival records."""
        lines = []
        for item in memory_records:
            if isinstance(item, dict):
                key = item.get("key") or item.get("id") or "memory"
                val = item.get("value") or item.get("text") or item.get("content") or ""
                cat = item.get("category", "")
                cat_tag = f" [{cat}]" if cat else ""
                lines.append(f"- {key}: {val}{cat_tag}")
            else:
                lines.append(f"- {str(item).strip()}")
        return "\n".join(lines)

    def _format_knowledge(self, knowledge_chunks: List[Union[Dict[str, Any], str]]) -> str:
        """Format L3 retrieved knowledge chunks with provenance and score."""
        blocks = []
        for idx, item in enumerate(knowledge_chunks, 1):
            if isinstance(item, dict):
                content = item.get("content") or item.get("text") or ""
                source = item.get("source") or item.get("doc_id") or f"doc_{idx}"
                score = item.get("score")
                score_str = f" (relevance: {score:.2f})" if isinstance(score, (int, float)) else ""
                blocks.append(f"[Source: {source}{score_str}]\n{content.strip()}")
            else:
                blocks.append(f"[Item {idx}]\n{str(item).strip()}")
        return "\n\n".join(blocks)

    def _format_tools(self, tools: List[Union[Dict[str, Any], str]]) -> str:
        """Format L5 active tools with signatures and descriptions."""
        lines = []
        for tool in tools:
            if isinstance(item := tool, dict):
                name = item.get("name", "tool")
                desc = item.get("description", "")
                params = item.get("parameters", {})
                param_keys = list(params.get("properties", {}).keys()) if isinstance(params, dict) else []
                lines.append(f"- {name}({', '.join(param_keys)}): {desc}")
            else:
                lines.append(f"- {str(tool).strip()}")
        return "\n".join(lines)

    def _format_conversation(self, history: List[Dict[str, str]]) -> str:
        """Format conversation turns."""
        turns = []
        for t in history:
            role = t.get("role", "user").capitalize()
            content = t.get("content", "").strip()
            turns.append(f"{role}: {content}")
        return "\n\n".join(turns)

    def _prune_section(self, text: str, max_tokens: int) -> Tuple[str, bool]:
        """Prune text block to fit within token limit."""
        if not text or max_tokens <= 0:
            return "", bool(text)
        current_tokens = self.count_tokens(text)
        if current_tokens <= max_tokens:
            return text, False

        # Try line-by-line pruning
        lines = text.split("\n")
        retained = []
        for line in lines:
            candidate = "\n".join(retained + [line])
            if self.count_tokens(candidate) > max_tokens:
                break
            retained.append(line)

        if retained:
            return "\n".join(retained), True

        # Fallback character slicing
        ratio = max_tokens / max(1, current_tokens)
        slice_len = int(len(text) * ratio * 0.9)
        return text[:slice_len] + "...", True

    def assemble(
        self,
        system_instructions: Optional[str] = None,
        memory_records: Optional[List[Union[Dict[str, Any], str]]] = None,
        retrieved_knowledge: Optional[List[Union[Dict[str, Any], str]]] = None,
        active_tools: Optional[List[Union[Dict[str, Any], str]]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        situational_context: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> AssembledContext:
        """Feature 9.01, 9.02, 9.03: Main entry point for context assembly.

        Assembles context while strictly enforcing source budgets, multi-tier
        prioritization, and total token caps.
        """
        memory_records = memory_records or []
        retrieved_knowledge = retrieved_knowledge or []
        active_tools = active_tools or []
        conversation_history = conversation_history or []

        # 1. Format raw strings for each component
        system_str = (system_instructions or "").strip()
        situational_str = (situational_context or "").strip()
        memory_str = self._format_memory(memory_records)
        knowledge_str = self._format_knowledge(retrieved_knowledge)
        tools_str = self._format_tools(active_tools)

        # 2. Estimate raw token demands
        tokens_system = self.count_tokens(system_str)
        tokens_situational = self.count_tokens(situational_str)
        tokens_memory = self.count_tokens(memory_str)
        tokens_knowledge = self.count_tokens(knowledge_str)
        tokens_tools = self.count_tokens(tools_str)
        tokens_history = sum(
            self.count_tokens(f"{t.get('role')}: {t.get('content')}") for t in conversation_history
        )

        total_raw_tokens = (
            tokens_system
            + tokens_situational
            + tokens_memory
            + tokens_knowledge
            + tokens_tools
            + tokens_history
        )

        # 3. Choose strategy (9.05)
        strategy = self.choose_strategy(total_raw_tokens)

        # 4. Handle Conversation Compaction (9.04)
        conv_budget = self.config.conversation_budget
        compacted_history, was_compacted = self.compact_conversation(
            conversation_history, max_tokens=conv_budget
        )
        conversation_str = self._format_conversation(compacted_history)

        # 5. Token budget allocation per source (9.02)
        # Allocate base budgets
        b_system = min(self.config.system_budget, tokens_system)
        b_situational = min(self.config.situational_budget, tokens_situational)
        b_tools = min(self.config.tools_budget, tokens_tools)
        b_memory = self.config.memory_budget
        b_knowledge = self.config.knowledge_budget
        b_conv = conv_budget

        was_pruned = False

        # Prune memory if exceeds budget
        memory_str, pruned_mem = self._prune_section(memory_str, b_memory)
        # Prune knowledge if exceeds budget
        knowledge_str, pruned_know = self._prune_section(knowledge_str, b_knowledge)
        # Prune tools if exceeds budget
        tools_str, pruned_tools = self._prune_section(tools_str, b_tools)

        was_pruned = was_pruned or pruned_mem or pruned_know or pruned_tools or was_compacted

        # 6. Global Prioritization Pruning (9.03)
        # Build prompt sections in priority order:
        # Priority 1: System + Situational Instructions
        # Priority 2: Active Tools
        # Priority 3: Working Conversation History
        # Priority 4: Active Core Memory
        # Priority 5: Retrieved Knowledge Chunks
        def build_full_prompt(
            sys_t: str, sit_t: str, tool_t: str, conv_t: str, mem_t: str, know_t: str
        ) -> str:
            sections = []
            if sys_t:
                sections.append(f"<system_instructions>\n{sys_t}\n</system_instructions>")
            if sit_t:
                sections.append(f"<situational_context>\n{sit_t}\n</situational_context>")
            if tool_t:
                sections.append(f"<active_tools>\n{tool_t}\n</active_tools>")
            if mem_t:
                sections.append(f"<memory_context>\n{mem_t}\n</memory_context>")
            if know_t:
                sections.append(f"<retrieved_knowledge>\n{know_t}\n</retrieved_knowledge>")
            if conv_t:
                sections.append(f"<conversation_history>\n{conv_t}\n</conversation_history>")
            return "\n\n".join(sections)

        full_prompt = build_full_prompt(
            system_str, situational_str, tools_str, conversation_str, memory_str, knowledge_str
        )
        total_tokens = self.count_tokens(full_prompt)

        # Global trimming loop if still over total_budget
        while total_tokens > self.config.total_budget:
            was_pruned = True
            # Level 1: Trim knowledge first
            if knowledge_str:
                current_know_tokens = self.count_tokens(knowledge_str)
                excess = total_tokens - self.config.total_budget
                new_target = max(0, current_know_tokens - excess - 20)
                knowledge_str, _ = self._prune_section(knowledge_str, new_target)
            # Level 2: Trim memory second
            elif memory_str:
                current_mem_tokens = self.count_tokens(memory_str)
                excess = total_tokens - self.config.total_budget
                new_target = max(0, current_mem_tokens - excess - 20)
                memory_str, _ = self._prune_section(memory_str, new_target)
            # Level 3: Trim conversation history
            elif conversation_str:
                current_conv_tokens = self.count_tokens(conversation_str)
                excess = total_tokens - self.config.total_budget
                new_target = max(0, current_conv_tokens - excess - 20)
                conversation_str, _ = self._prune_section(conversation_str, new_target)
            else:
                break

            full_prompt = build_full_prompt(
                system_str, situational_str, tools_str, conversation_str, memory_str, knowledge_str
            )
            total_tokens = self.count_tokens(full_prompt)

        # 7. Collect metadata and token breakdown
        token_breakdown = {
            "system": self.count_tokens(system_str),
            "situational": self.count_tokens(situational_str),
            "tools": self.count_tokens(tools_str),
            "memory": self.count_tokens(memory_str),
            "knowledge": self.count_tokens(knowledge_str),
            "conversation": self.count_tokens(conversation_str),
            "total": total_tokens,
        }

        sources = []
        if system_str:
            sources.append(ContextSource.SYSTEM.value)
        if situational_str:
            sources.append(ContextSource.SITUATIONAL.value)
        if tools_str:
            sources.append(ContextSource.TOOLS.value)
        if memory_str:
            sources.append(ContextSource.MEMORY.value)
        if knowledge_str:
            sources.append(ContextSource.KNOWLEDGE.value)
        if conversation_str:
            sources.append(ContextSource.CONVERSATION.value)

        return AssembledContext(
            system_prompt=system_str,
            memory_context=memory_str,
            knowledge_context=knowledge_str,
            tools_context=tools_str,
            conversation_context=conversation_str,
            full_prompt=full_prompt,
            token_counts=token_breakdown,
            total_tokens=total_tokens,
            sources_included=sources,
            pruned=was_pruned,
            compacted=was_compacted,
            strategy_used=strategy,
            metadata={
                "user_id": user_id,
                "session_id": session_id,
                "raw_input_tokens": total_raw_tokens,
                "budget_cap": self.config.total_budget,
            },
        )
