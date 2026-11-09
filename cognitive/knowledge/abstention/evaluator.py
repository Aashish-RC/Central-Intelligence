"""Evidence Grounding Evaluator for Abstention Logic (Feature 3.35)."""

import re
from typing import List, Set, Tuple
from knowledge.abstention.models import (
    AbstentionVerdict,
    EvidenceChunkEvaluation,
    GroundingEvaluation,
)


class GroundingEvidenceEvaluator:
    """Evaluates whether retrieved knowledge chunks sufficiently ground a user query."""

    def __init__(
        self,
        default_threshold: float = 0.65,
        relevance_weight: float = 0.5,
        coverage_weight: float = 0.5,
        conflict_penalty: float = 0.3,
    ):
        self.default_threshold = default_threshold
        self.relevance_weight = relevance_weight
        self.coverage_weight = coverage_weight
        self.conflict_penalty = conflict_penalty

    def extract_salient_terms(self, text: str) -> Set[str]:
        """Extracts informative keywords from query or passage."""
        stopwords = {
            "what", "where", "when", "which", "who", "whom", "this", "that", "these",
            "those", "have", "from", "with", "about", "into", "through", "after", "before",
            "does", "explain", "describe", "tell", "show", "give", "could", "would", "should",
            "the", "and", "for", "are", "was", "were", "been", "being",
        }
        tokens = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower())
        return {t for t in tokens if t not in stopwords}

    def evaluate(
        self,
        query: str,
        evidence_chunks: List[str],
        threshold: float = None,
    ) -> GroundingEvaluation:
        """Evaluates retrieved chunks against query to determine grounding and abstention."""
        th = threshold if threshold is not None else self.default_threshold
        query_terms = self.extract_salient_terms(query)

        # Empty evidence -> definite abstention
        if not evidence_chunks or len(evidence_chunks) == 0:
            return GroundingEvaluation(
                query=query,
                verdict=AbstentionVerdict.ABSTAIN,
                confidence_score=0.0,
                threshold=th,
                relevance_score=0.0,
                coverage_score=0.0,
                conflict_score=0.0,
                chunks_evaluated=[],
                reason="No evidence passages were retrieved for the query.",
                abstention_message="I cannot answer this question because no relevant verified documents were found.",
            )

        chunk_evals: List[EvidenceChunkEvaluation] = []
        covered_query_terms: Set[str] = set()
        max_relevance = 0.0

        for idx, chunk in enumerate(evidence_chunks):
            chunk_terms = self.extract_salient_terms(chunk)
            matched = query_terms.intersection(chunk_terms)
            covered_query_terms.update(matched)

            # Relevance of this chunk
            chunk_rel = len(matched) / max(len(query_terms), 1)
            if chunk_rel > max_relevance:
                max_relevance = chunk_rel

            chunk_evals.append(
                EvidenceChunkEvaluation(
                    chunk_index=idx,
                    text=chunk,
                    relevance_score=round(chunk_rel, 3),
                    matched_terms=list(matched),
                    has_contradiction=False,
                )
            )

        # Coverage score
        coverage = len(covered_query_terms) / max(len(query_terms), 1)

        # Contradiction detection across chunks
        conflict = self.detect_conflicts(evidence_chunks)

        # Composite Grounding Confidence with contradiction dampening
        conflict_dampening = max(0.0, 1.0 - (0.6 * conflict))
        base_grounding = (self.relevance_weight * max_relevance) + (self.coverage_weight * coverage)
        raw_confidence = (base_grounding * conflict_dampening) - (self.conflict_penalty * conflict)
        confidence = max(0.0, min(1.0, round(raw_confidence, 3)))

        # Verdict
        if confidence >= th:
            verdict = AbstentionVerdict.ANSWER
            reason = f"Grounding confidence ({confidence:.2f}) meets threshold ({th:.2f})."
            abstention_msg = None
        elif confidence >= th * 0.6:
            verdict = AbstentionVerdict.PARTIAL
            reason = (
                f"Partial grounding confidence ({confidence:.2f}) is below threshold ({th:.2f}). "
                f"Missing coverage for terms: {list(query_terms - covered_query_terms)}."
            )
            abstention_msg = (
                "The available documents only partially cover this topic. "
                "I can provide a limited overview, but some details cannot be verified."
            )
        else:
            verdict = AbstentionVerdict.ABSTAIN
            reason = (
                f"Insufficient grounding confidence ({confidence:.2f} < {th:.2f}). "
                "Retrieved passages do not answer the specific query."
            )
            abstention_msg = (
                "I do not have sufficient verified knowledge in the knowledge base "
                "to answer this question accurately without risking hallucination."
            )

        return GroundingEvaluation(
            query=query,
            verdict=verdict,
            confidence_score=confidence,
            threshold=th,
            relevance_score=round(max_relevance, 3),
            coverage_score=round(coverage, 3),
            conflict_score=round(conflict, 3),
            chunks_evaluated=chunk_evals,
            reason=reason,
            abstention_message=abstention_msg,
        )

    def detect_conflicts(self, chunks: List[str]) -> float:
        """Heuristic contradiction detector across multiple evidence chunks."""
        if len(chunks) <= 1:
            return 0.0

        contradiction_markers = [
            (r"\bnot\b", r"\bis\b"),
            (r"\bdeprecated\b", r"\brecommended\b"),
            (r"\bforbidden\b", r"\ballowed\b"),
            (r"\bdisabled\b", r"\benabled\b"),
            (r"\bfalse\b", r"\btrue\b"),
        ]

        conflicts_found = 0
        for pattern_neg, pattern_pos in contradiction_markers:
            has_neg = any(re.search(pattern_neg, c, re.IGNORECASE) for c in chunks)
            has_pos = any(re.search(pattern_pos, c, re.IGNORECASE) for c in chunks)
            if has_neg and has_pos:
                conflicts_found += 1

        return min(1.0, conflicts_found * 0.35)
