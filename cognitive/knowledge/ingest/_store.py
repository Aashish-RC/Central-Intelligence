"""Shared searchable chunk store for L3 Knowledge ingestion modules."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class KnowledgeChunk:
    """Indexed knowledge fragment from any modality."""

    chunk_id: str
    source_id: str
    modality: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeHit:
    """Ranked search match returned by InMemoryKnowledgeIndex."""

    chunk: KnowledgeChunk
    score: float
    matched_terms: List[str] = field(default_factory=list)


class InMemoryKnowledgeIndex:
    """Lightweight BM25-inspired in-memory index for ingested knowledge chunks."""

    def __init__(self) -> None:
        self._chunks: Dict[str, KnowledgeChunk] = {}

    def add(self, chunk: KnowledgeChunk) -> None:
        self._chunks[chunk.chunk_id] = chunk

    def delete_source(self, source_id: str) -> int:
        to_delete = [cid for cid, ch in self._chunks.items() if ch.source_id == source_id]
        for cid in to_delete:
            del self._chunks[cid]
        return len(to_delete)

    def delete_chunks(self, chunk_ids: List[str]) -> None:
        for cid in chunk_ids:
            self._chunks.pop(cid, None)

    def list_chunks(self, source_id: Optional[str] = None) -> List[KnowledgeChunk]:
        if source_id is None:
            return list(self._chunks.values())
        return [c for c in self._chunks.values() if c.source_id == source_id]

    def search(self, query: str, top_k: int = 5, modality: Optional[str] = None) -> List[KnowledgeHit]:
        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        docs = [
            c for c in self._chunks.values() if modality is None or c.modality == modality
        ]
        if not docs:
            return []

        n_docs = len(docs)
        df: Counter[str] = Counter()
        doc_tokens: Dict[str, List[str]] = {}
        for ch in docs:
            toks = tokenize(ch.text)
            doc_tokens[ch.chunk_id] = toks
            for term in set(toks):
                df[term] += 1

        q_lower = query.lower().strip()
        hits: List[KnowledgeHit] = []
        for ch in docs:
            toks = doc_tokens[ch.chunk_id]
            tf = Counter(toks)
            score = 0.0
            matched: List[str] = []
            for qt in set(q_tokens):
                if tf[qt] > 0:
                    idf = math.log((n_docs + 1.0) / (df[qt] + 0.5)) + 1.0
                    score += (1.0 + math.log(tf[qt])) * idf
                    matched.append(qt)
            if q_lower and q_lower in ch.text.lower():
                score += 2.0
            if score > 0:
                hits.append(KnowledgeHit(chunk=ch, score=round(score, 4), matched_terms=sorted(matched)))

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

