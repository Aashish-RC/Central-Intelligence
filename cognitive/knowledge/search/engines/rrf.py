"""Reciprocal Rank Fusion (RRF) combiner for hybrid search."""

import re
from typing import Dict, List, Set, Tuple
from ..core.interfaces import BaseRankFusion
from ..core.models import SearchDocument, SearchResult


class ReciprocalRankFusion(BaseRankFusion):
    """Combines lexical BM25 and dense vector ranking candidate lists using RRF."""

    def fuse(
        self,
        lexical_hits: List[Tuple[SearchDocument, float]],
        vector_hits: List[Tuple[SearchDocument, float]],
        k: int = 60,
        alpha: float = 0.5,
        limit: int = 20,
    ) -> List[SearchResult]:
        """Calculates blended RRF scores:
        score(d) = (1 - alpha) * 1 / (k + rank_lex) + alpha * 1 / (k + rank_vec)
        """
        doc_map: Dict[str, SearchDocument] = {}
        lexical_ranks: Dict[str, int] = {}
        vector_ranks: Dict[str, int] = {}

        # 1-indexed ranks
        for rank, (doc, _score) in enumerate(lexical_hits, 1):
            doc_map[doc.id] = doc
            lexical_ranks[doc.id] = rank

        for rank, (doc, _score) in enumerate(vector_hits, 1):
            doc_map[doc.id] = doc
            vector_ranks[doc.id] = rank

        scores: Dict[str, float] = {}
        weight_lex = 1.0 - alpha
        weight_vec = alpha

        all_doc_ids: Set[str] = set(lexical_ranks.keys()).union(vector_ranks.keys())
        for doc_id in all_doc_ids:
            score = 0.0
            if doc_id in lexical_ranks:
                score += weight_lex * (1.0 / (k + lexical_ranks[doc_id]))
            if doc_id in vector_ranks:
                score += weight_vec * (1.0 / (k + vector_ranks[doc_id]))
            scores[doc_id] = score

        # Sort descending by fused score
        sorted_ids = sorted(all_doc_ids, key=lambda did: scores[did], reverse=True)[:limit]

        results: List[SearchResult] = []
        for did in sorted_ids:
            doc = doc_map[did]
            # Simple keyword highlights
            highlights = self._generate_highlights(doc.content)
            results.append(
                SearchResult(
                    document=doc,
                    rrf_score=round(scores[did], 6),
                    lexical_rank=lexical_ranks.get(did),
                    vector_rank=vector_ranks.get(did),
                    highlights=highlights,
                )
            )

        return results

    @staticmethod
    def _generate_highlights(content: str, max_chars: int = 150) -> List[str]:
        if not content:
            return []
        cleaned = re.sub(r"\s+", " ", content).strip()
        if len(cleaned) <= max_chars:
            return [cleaned]
        return [cleaned[:max_chars] + "..."]
