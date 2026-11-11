"""Reciprocal Rank Fusion (RRF) combiner for hybrid search."""

import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from ..core.interfaces import BaseRankFusion
from ..core.models import SearchDocument, SearchResult


_TOKEN_RE = re.compile(r"[a-z0-9]+")


class CrossEncoderReranker:
    """Post-RRF cross-encoder re-ranker (L3 Feature 3.32).

    Scores `(query, document)` pairs jointly using either a supplied cross-encoder
    callable or a deterministic lexical-bigram + exact-phrase + title overlap scorer.
    """

    def __init__(self, score_fn: Optional[Callable[[str, str], float]] = None) -> None:
        self._score_fn = score_fn

    def score_pair(self, query: str, doc: SearchDocument) -> float:
        doc_text = f"{doc.title}\n{doc.content}".strip()
        if self._score_fn is not None:
            return float(self._score_fn(query, doc_text))

        q_tokens = _TOKEN_RE.findall(query.lower())
        if not q_tokens:
            return 0.0
        title_tokens = _TOKEN_RE.findall(doc.title.lower())
        body_tokens = _TOKEN_RE.findall(doc.content.lower())
        all_tokens = title_tokens + body_tokens

        q_set = set(q_tokens)
        overlap = len(q_set.intersection(all_tokens)) / max(len(q_set), 1)
        title_overlap = len(q_set.intersection(title_tokens)) / max(len(q_set), 1)

        # Bigram co-occurrence captures query-document order alignment
        q_bigrams = {tuple(q_tokens[i : i + 2]) for i in range(max(0, len(q_tokens) - 1))}
        doc_bigrams = {tuple(all_tokens[i : i + 2]) for i in range(max(0, len(all_tokens) - 1))}
        bigram_score = (len(q_bigrams.intersection(doc_bigrams)) / len(q_bigrams)) if q_bigrams else 0.0

        exact_phrase = 0.35 if query.strip().lower() in doc_text.lower() else 0.0
        return round(0.40 * overlap + 0.25 * bigram_score + 0.20 * title_overlap + exact_phrase, 6)

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: Optional[int] = None,
    ) -> List[SearchResult]:
        if not results or not query.strip():
            return results[:top_k] if top_k is not None else results

        scored: List[Tuple[float, SearchResult]] = []
        for res in results:
            ce_score = self.score_pair(query, res.document)
            # Blend normalized cross-encoder affinity with initial RRF signal
            combined = round(0.75 * ce_score + 0.25 * res.rrf_score, 6)
            updated = res.model_copy(update={"rrf_score": combined})
            scored.append((combined, updated))

        scored.sort(key=lambda item: item[0], reverse=True)
        reranked = [item[1] for item in scored]
        return reranked[:top_k] if top_k is not None else reranked


class ReciprocalRankFusion(BaseRankFusion):
    """Combines lexical BM25 and dense vector ranking candidate lists using RRF."""

    def __init__(self, reranker: Optional[CrossEncoderReranker] = None) -> None:
        self.reranker = reranker or CrossEncoderReranker()

    def fuse(
        self,
        lexical_hits: List[Tuple[SearchDocument, float]],
        vector_hits: List[Tuple[SearchDocument, float]],
        graph_hits: Optional[List[Tuple[SearchDocument, float]]] = None,
        k: int = 60,
        alpha: float = 0.5,
        weights: Optional[Tuple[float, float, float]] = None,
        limit: int = 20,
        user_id: Optional[str] = None,
        openfga_client: Optional[Any] = None,
        query: Optional[str] = None,
        rerank: bool = False,
    ) -> List[SearchResult]:
        """Calculates blended RRF scores across lexical, vector, and graph candidate lists:
        score(d) = w_lex * 1 / (k + rank_lex) + w_vec * 1 / (k + rank_vec) + w_graph * 1 / (k + rank_graph)
        """
        doc_map: Dict[str, SearchDocument] = {}
        lexical_ranks: Dict[str, int] = {}
        vector_ranks: Dict[str, int] = {}
        graph_ranks: Dict[str, int] = {}

        # 1-indexed ranks
        for rank, (doc, _score) in enumerate(lexical_hits, 1):
            doc_map[doc.id] = doc
            lexical_ranks[doc.id] = rank

        for rank, (doc, _score) in enumerate(vector_hits, 1):
            doc_map[doc.id] = doc
            vector_ranks[doc.id] = rank

        if graph_hits:
            for rank, (doc, _score) in enumerate(graph_hits, 1):
                doc_map[doc.id] = doc
                graph_ranks[doc.id] = rank

        scores: Dict[str, float] = {}
        if weights is not None:
            weight_lex, weight_vec, weight_graph = weights
        elif graph_hits:
            # 3-source balanced weighting
            weight_lex = (1.0 - alpha) * 0.5
            weight_vec = alpha * 0.5
            weight_graph = 0.5
        else:
            weight_lex = 1.0 - alpha
            weight_vec = alpha
            weight_graph = 0.0

        all_doc_ids: Set[str] = set(lexical_ranks.keys()).union(vector_ranks.keys()).union(graph_ranks.keys())
        for doc_id in all_doc_ids:
            score = 0.0
            if doc_id in lexical_ranks:
                score += weight_lex * (1.0 / (k + lexical_ranks[doc_id]))
            if doc_id in vector_ranks:
                score += weight_vec * (1.0 / (k + vector_ranks[doc_id]))
            if doc_id in graph_ranks:
                score += weight_graph * (1.0 / (k + graph_ranks[doc_id]))
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
                    graph_rank=graph_ranks.get(did),
                    highlights=highlights,
                )
            )

        if user_id:
            try:
                from cognitive.knowledge.access_control.openfga_bridge import filter_results_by_permission
                results = filter_results_by_permission(results, user_id=user_id, openfga_client=openfga_client)
            except ImportError:
                try:
                    from knowledge.access_control.openfga_bridge import filter_results_by_permission
                    results = filter_results_by_permission(results, user_id=user_id, openfga_client=openfga_client)
                except ImportError:
                    pass

        if rerank and query:
            results = self.reranker.rerank(query, results, top_k=limit)

        return results

    @staticmethod
    def _generate_highlights(content: str, max_chars: int = 150) -> List[str]:
        if not content:
            return []
        cleaned = re.sub(r"\s+", " ", content).strip()
        if len(cleaned) <= max_chars:
            return [cleaned]
        return [cleaned[:max_chars] + "..."]
