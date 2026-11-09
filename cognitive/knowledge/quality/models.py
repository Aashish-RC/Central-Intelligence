"""Data models for Source Quality & Authority Scoring (Feature 3.43)."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SourceQualityTier(str, Enum):
    TIER_1_AUTHORITATIVE = "tier_1_authoritative"
    TIER_2_RELIABLE = "tier_2_reliable"
    TIER_3_UNVERIFIED = "tier_3_unverified"
    TIER_4_LOW_QUALITY = "tier_4_low_quality"


class QualitySignal(BaseModel):
    name: str
    impact: float        # positive or negative delta
    category: str        # 'domain', 'content', 'freshness', 'provenance'
    description: str


class SourceQualityScore(BaseModel):
    source_url_or_id: str
    overall_score: float = Field(..., ge=0.0, le=1.0)
    authority_score: float = Field(..., ge=0.0, le=1.0)
    content_quality_score: float = Field(..., ge=0.0, le=1.0)
    freshness_score: float = Field(default=0.8, ge=0.0, le=1.0)
    tier: SourceQualityTier
    signals: List[QualitySignal] = Field(default_factory=list)
    llm_judge_verdict: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
