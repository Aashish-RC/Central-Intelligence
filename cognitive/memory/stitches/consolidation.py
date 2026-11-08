"""Phase 4: Autonomous Consolidation Engine ("REM Sleep Cycle") and Fact Decay Scoring."""

from datetime import datetime, timezone
import math
from typing import List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from memory.core.models import MemoryRecord, Turn, FactItem, utc_now
from memory.core.interfaces import BaseWorkingMemory, BaseFactStore, BaseVectorStore, BaseEmbedder
from memory.config import MemoryConfig


class ConsolidationResult(BaseModel):
    """Metrics and outputs from a consolidation cycle."""
    session_id: str
    user_id: str
    turns_consolidated: int
    summary_record_id: Optional[str] = None
    summary_text: Optional[str] = None
    purged_from_working: bool = True


class ConsolidationEngine:
    """Asynchronous/background engine that processes raw session history, synthesizes long-term
    episodic milestones into Tier 3 vector storage, and applies soft decay scoring.
    """

    def __init__(
        self,
        working_memory: BaseWorkingMemory,
        fact_store: BaseFactStore,
        vector_store: BaseVectorStore,
        embedder: BaseEmbedder,
        config: Optional[MemoryConfig] = None,
    ):
        self._working = working_memory
        self._facts = fact_store
        self._vectors = vector_store
        self._embedder = embedder
        if config is None:
            from memory.config import default_config
            config = default_config
        self._config = config

    def calculate_decay_score(
        self,
        last_accessed_at: datetime,
        base_confidence: float = 1.0,
        access_count: int = 0,
        half_life_days: Optional[float] = None,
    ) -> float:
        """Compute time-decayed relevance score with frequency reinforcement.
        
        Score = base_confidence * (0.5 ^ (elapsed_days / half_life)) * log2(2 + access_count)
        """
        if half_life_days is None:
            half_life_days = self._config.decay_half_life_days

        now = utc_now()
        # Handle naive datetime gracefully
        if last_accessed_at.tzinfo is None:
            last_accessed_at = last_accessed_at.replace(tzinfo=timezone.utc)

        elapsed_seconds = max(0.0, (now - last_accessed_at).total_seconds())
        elapsed_days = elapsed_seconds / 86400.0

        # Exponential decay factor
        decay = math.pow(0.5, elapsed_days / max(0.1, half_life_days))
        # Frequency bonus: memories accessed multiple times resist decay
        freq_bonus = math.log2(2.0 + access_count)

        return float(base_confidence * decay * freq_bonus)

    def consolidate_session(self, user_id: str, session_id: str) -> ConsolidationResult:
        """Compresses all turns from a session into a semantic milestone in Tier 3,
        then purges the Tier 1 working buffer.
        """
        turns = self._working.get_session_turns(session_id)
        if not turns:
            return ConsolidationResult(
                session_id=session_id,
                user_id=user_id,
                turns_consolidated=0,
                purged_from_working=True,
            )

        # Summarize conversation milestones
        bullet_points = []
        for t in turns:
            preview = t.content.strip().replace("\n", " ")
            if len(preview) > 120:
                preview = preview[:117] + "..."
            bullet_points.append(f"{t.role.value}: {preview}")

        summary_text = f"Session {session_id} recap ({len(turns)} turns):\n" + "\n".join(bullet_points[:20])

        # Generate embedding and store in Tier 3
        summary_emb = self._embedder.embed_text(summary_text)
        record_id = uuid4()
        record = MemoryRecord(
            id=record_id,
            user_id=user_id,
            session_id=session_id,
            text=summary_text,
            embedding=summary_emb,
            metadata={
                "consolidated_from": session_id,
                "turn_count": len(turns),
                "type": "session_consolidation_milestone",
            },
        )
        self._vectors.upsert_vectors([record])

        # Purge Tier 1 working memory buffer
        self._working.clear(session_id)

        return ConsolidationResult(
            session_id=session_id,
            user_id=user_id,
            turns_consolidated=len(turns),
            summary_record_id=str(record_id),
            summary_text=summary_text,
            purged_from_working=True,
        )
