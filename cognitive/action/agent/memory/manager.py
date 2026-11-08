"""Unified Facade: remember() & recall() interface for Fused Agent Memory."""

from typing import Any, Dict, List, Optional

from .tiers.working import WorkingMemoryTier
from .tiers.facts import FactStoreTier
from .tiers.vector import VectorMemoryTier
from .cognition import MemoryCognition, MemoryContextBlock


class MemoryManager:
    """Unified Facade orchestrating Tier 1 (Working), Tier 2 (Facts), and Tier 3 (Vectors)."""

    def __init__(
        self,
        working: Optional[WorkingMemoryTier] = None,
        facts: Optional[FactStoreTier] = None,
        vector: Optional[VectorMemoryTier] = None,
        canonical_engine: Optional[Any] = None,
    ):
        self.working = working or WorkingMemoryTier()
        self.facts = facts or FactStoreTier()
        self.vector = vector or VectorMemoryTier()
        self.cognition = MemoryCognition()
        self.canonical_engine = canonical_engine

    async def remember(
        self,
        session_id: str,
        role: str,
        content: str,
        namespace: str = "default",
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Record turn into working memory, extract persistent facts, and index into vector space."""
        # 1. Append to working session memory
        turn = self.working.append_turn(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata,
        )

        # 2. Extract facts via Mem0-style cognition
        extracted = self.cognition.extract_facts(content)
        saved_fact_ids = []
        for fact in extracted:
            fid = self.facts.save_fact(
                namespace=namespace,
                entity_key=fact.entity_key,
                fact_text=fact.fact_text,
                category=fact.category,
                confidence=fact.confidence,
                metadata={"session_id": session_id, "source_role": role},
            )
            saved_fact_ids.append(fid)

        # 3. Store meaningful assistant or user thoughts into semantic vector index
        vector_doc_id = None
        if len(content.split()) >= 4:
            vector_doc_id = self.vector.insert(
                text=f"{role.capitalize()}: {content}",
                namespace=namespace,
                metadata={"session_id": session_id, "role": role},
            )

        # 4. Delegation: persist to canonical memory.engine.MemoryEngine
        canonical_res = None
        engine = self.canonical_engine
        if engine is None:
            try:
                from memory.engine import MemoryEngine
                engine = MemoryEngine()
                self.canonical_engine = engine
            except Exception:
                engine = None

        if engine is not None:
            try:
                from memory.core.models import TurnRole
                try:
                    turn_role = TurnRole(role.lower())
                except (ValueError, AttributeError):
                    turn_role = TurnRole.USER

                canonical_res = engine.remember(
                    user_id=namespace,
                    text=content,
                    session_id=session_id,
                    role=turn_role,
                    project_id=namespace,
                    metadata=metadata,
                )
            except Exception:
                pass

        return {
            "turn": turn,
            "extracted_facts": len(saved_fact_ids),
            "vector_indexed": vector_doc_id is not None,
            "canonical_synced": canonical_res is not None,
        }

    async def recall(
        self,
        query: str,
        namespace: str = "default",
        session_id: Optional[str] = None,
        top_k: int = 5,
        include_working: bool = True,
    ) -> MemoryContextBlock:
        """Recall 3-tier memory context for an upcoming agent reasoning turn."""
        # 1. Working memory turns
        recent_turns: List[Dict[str, Any]] = []
        if include_working and session_id:
            recent_turns = self.working.get_recent_turns(session_id=session_id, limit=10)

        # 2. Facts and constraints
        stored_facts = self.facts.query_facts(namespace=namespace, limit=20)

        # 3. Semantic vector search
        semantic_matches = self.vector.search(
            query=query,
            namespace=namespace,
            top_k=top_k,
        )

        return self.cognition.synthesize_context(
            recent_turns=recent_turns,
            facts=stored_facts,
            semantic_matches=semantic_matches,
        )


# Global shared instance
default_memory_manager = MemoryManager()
