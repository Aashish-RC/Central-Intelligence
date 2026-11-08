"""Abstract interfaces for Pheonix Empirical Recommender components."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from .models import (
    BenchmarkResult,
    CandidateScore,
    ModelCandidate,
    RecommendationDecision,
    TaskProfile,
    ToolCandidate,
)


class BaseTelemetryScorer(ABC):
    """Interface for calculating empirical candidate scores from past executions."""

    @abstractmethod
    def score_model(
        self, candidate: ModelCandidate, task: TaskProfile
    ) -> CandidateScore:
        pass

    @abstractmethod
    def score_tool(
        self, candidate: ToolCandidate, task: TaskProfile
    ) -> CandidateScore:
        pass

    @abstractmethod
    def record_execution(
        self,
        candidate_id: str,
        latency_ms: float,
        cost_usd: float,
        success: bool,
        quality_rating: Optional[float] = None,
    ) -> None:
        pass


class BaseSecondOpinionArbiter(ABC):
    """Interface for evaluating confidence margins and arbitrating consensus."""

    @abstractmethod
    def should_trigger_second_opinion(
        self,
        top_score: CandidateScore,
        runner_up: Optional[CandidateScore],
        task: TaskProfile,
    ) -> bool:
        pass

    @abstractmethod
    def arbitrate(
        self,
        top_candidate: CandidateScore,
        runner_up: CandidateScore,
        task: TaskProfile,
    ) -> tuple[str, str]:
        """Returns (chosen_candidate_id, explanation_notes)."""
        pass


class BaseRecommenderService(ABC):
    """Interface for top-level recommendation decisions."""

    @abstractmethod
    def recommend_model(
        self, task: TaskProfile, candidates: List[ModelCandidate]
    ) -> RecommendationDecision:
        pass

    @abstractmethod
    def recommend_tool(
        self, task: TaskProfile, candidates: List[ToolCandidate]
    ) -> RecommendationDecision:
        pass


class BaseBenchmarkSuite(ABC):
    """Interface for benchmarking Auto picks versus Manual selections."""

    @abstractmethod
    def run_benchmark(
        self,
        tasks: List[TaskProfile],
        models: List[ModelCandidate],
        manual_fixed_candidate_id: str,
    ) -> BenchmarkResult:
        pass
