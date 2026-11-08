"""Core data models for Pheonix Empirical Recommender Engine."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskType(str, Enum):
    FAST_QUERY = "fast_query"
    REASONING = "reasoning"
    CODE_GENERATION = "code_generation"
    CREATIVE_WRITING = "creative_writing"
    TOOL_USE = "tool_use"
    EMBEDDING = "embedding"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OptimizationGoal(str, Enum):
    BALANCED = "balanced"
    MIN_COST = "min_cost"
    MIN_LATENCY = "min_latency"
    MAX_QUALITY = "max_quality"


class TaskProfile(BaseModel):
    task_id: str
    tenant_id: str = "default"
    task_type: TaskType = TaskType.FAST_QUERY
    risk_level: RiskLevel = RiskLevel.LOW
    goal: OptimizationGoal = OptimizationGoal.BALANCED
    max_latency_ms: Optional[float] = None
    max_cost_usd: Optional[float] = None
    required_capabilities: List[str] = Field(default_factory=list)
    prompt_token_estimate: int = 150
    expected_output_tokens: int = 250


class CandidateMetrics(BaseModel):
    total_invocations: int = 0
    successful_invocations: int = 0
    avg_latency_ms: float = 200.0
    p95_latency_ms: float = 400.0
    avg_cost_per_1k_tokens: float = 0.002
    quality_score: float = 0.85  # 0.0 to 1.0 scale

    @property
    def success_rate(self) -> float:
        if self.total_invocations == 0:
            return 1.0
        return self.successful_invocations / self.total_invocations


class ModelCandidate(BaseModel):
    provider: str
    model_name: str
    capabilities: List[str] = Field(default_factory=list)
    context_window: int = 128000
    cost_per_1k_input: float = 0.0015
    cost_per_1k_output: float = 0.002
    metrics: CandidateMetrics = Field(default_factory=CandidateMetrics)

    @property
    def candidate_id(self) -> str:
        return f"{self.provider}/{self.model_name}"


class ToolCandidate(BaseModel):
    tool_id: str
    name: str
    category: str = "general"
    avg_latency_ms: float = 50.0
    error_rate: float = 0.01
    token_overhead: int = 100
    capabilities: List[str] = Field(default_factory=list)


class ScoringWeights(BaseModel):
    cost_weight: float = 0.25
    latency_weight: float = 0.25
    quality_weight: float = 0.30
    reliability_weight: float = 0.20


class CandidateScore(BaseModel):
    candidate_id: str
    cost_score: float
    latency_score: float
    quality_score: float
    reliability_score: float
    composite_score: float
    estimated_cost_usd: float
    estimated_latency_ms: float


class RecommendationDecision(BaseModel):
    task_id: str
    tenant_id: str = "default"
    recommended_id: str
    candidate_type: str  # "model" or "tool"
    composite_score: float
    runner_up_id: Optional[str] = None
    runner_up_score: Optional[float] = None
    confidence_margin: float
    one_line_reason: str
    second_opinion_triggered: bool = False
    second_opinion_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class BenchmarkResult(BaseModel):
    tenant_id: str = "default"
    total_evaluations: int
    manual_total_cost_usd: float
    auto_total_cost_usd: float
    manual_avg_latency_ms: float
    auto_avg_latency_ms: float
    manual_success_rate: float
    auto_success_rate: float
    cost_reduction_percent: float
    latency_reduction_percent: float
    auto_wins: int
    manual_wins: int
    win_ratio: float
