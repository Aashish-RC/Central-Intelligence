"""Data models for Abstention Logic & Hallucination Prevention (Feature 3.35)."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AbstentionVerdict(str, Enum):
    ANSWER = "answer"
    ABSTAIN = "abstain"
    PARTIAL = "partial"


class EvidenceChunkEvaluation(BaseModel):
    chunk_index: int
    text: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    matched_terms: List[str] = Field(default_factory=list)
    has_contradiction: bool = False


class GroundingEvaluation(BaseModel):
    query: str
    verdict: AbstentionVerdict
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    coverage_score: float = Field(..., ge=0.0, le=1.0)
    conflict_score: float = Field(default=0.0, ge=0.0, le=1.0)
    chunks_evaluated: List[EvidenceChunkEvaluation] = Field(default_factory=list)
    reason: str
    abstention_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
