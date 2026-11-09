"""Abstention Engine orchestrating refusal vs grounded generation (Feature 3.35)."""

from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from knowledge.abstention.models import AbstentionVerdict, GroundingEvaluation
from knowledge.abstention.evaluator import GroundingEvidenceEvaluator


class GroundedExecutionResult(BaseModel):
    query: str
    output_text: str
    verdict: AbstentionVerdict
    abstained: bool
    evaluation: GroundingEvaluation
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AbstentionEngine:
    """Safeguard engine that triggers principled refusal when evidence is insufficient."""

    def __init__(
        self,
        evaluator: Optional[GroundingEvidenceEvaluator] = None,
        default_threshold: float = 0.65,
    ):
        self.evaluator = evaluator or GroundingEvidenceEvaluator(default_threshold=default_threshold)

    def evaluate_grounding(
        self,
        query: str,
        evidence_chunks: List[str],
        threshold: Optional[float] = None,
    ) -> GroundingEvaluation:
        """Evaluates whether retrieved passages are sufficient to ground an answer."""
        return self.evaluator.evaluate(
            query=query,
            evidence_chunks=evidence_chunks,
            threshold=threshold,
        )

    def execute_with_abstention(
        self,
        query: str,
        evidence_chunks: List[str],
        generator: Callable[[str, List[str]], str],
        threshold: Optional[float] = None,
    ) -> GroundedExecutionResult:
        """Executes LLM generation if evidence passes grounding threshold, otherwise abstains."""
        eval_result = self.evaluate_grounding(query, evidence_chunks, threshold=threshold)

        if eval_result.verdict == AbstentionVerdict.ABSTAIN:
            # Complete refusal — prevent hallucination
            return GroundedExecutionResult(
                query=query,
                output_text=eval_result.abstention_message or "Insufficient evidence to answer accurately.",
                verdict=AbstentionVerdict.ABSTAIN,
                abstained=True,
                evaluation=eval_result,
            )

        if eval_result.verdict == AbstentionVerdict.PARTIAL:
            # Partial answer with explicit disclaimer
            raw_output = generator(query, [c.text for c in eval_result.chunks_evaluated])
            disclaimer = f"[Notice: {eval_result.abstention_message}]\n\n"
            return GroundedExecutionResult(
                query=query,
                output_text=disclaimer + raw_output,
                verdict=AbstentionVerdict.PARTIAL,
                abstained=False,
                evaluation=eval_result,
            )

        # High confidence grounded answer
        output = generator(query, [c.text for c in eval_result.chunks_evaluated])
        return GroundedExecutionResult(
            query=query,
            output_text=output,
            verdict=AbstentionVerdict.ANSWER,
            abstained=False,
            evaluation=eval_result,
        )
