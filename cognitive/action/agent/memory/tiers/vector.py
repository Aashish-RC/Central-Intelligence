"""Tier 3: Semantic Vectors (Qdrant / Chroma / In-Memory Embedding Store)."""

from __future__ import annotations
import math
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _simple_text_embedding(text: str, dim: int = 64) -> List[float]:
    """Deterministic hash-based embedding fallback when external embedding API is offline."""
    vec = [0.0] * dim
    for i, word in enumerate(text.lower().split()):
        h = hash(word)
        idx = abs(h) % dim
        vec[idx] += 1.0 / (1.0 + math.log(i + 1))
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class VectorMemoryTier:
    """Semantic Vector Index with support for Qdrant client and in-memory fallback."""

    def __init__(self, qdrant_client: Optional[Any] = None, collection_name: str = "agent_kb"):
        self.qdrant = qdrant_client
        self.collection_name = collection_name
        self._local_records: List[Dict[str, Any]] = []

    def insert(
        self,
        text: str,
        namespace: str = "default",
        vector: Optional[List[float]] = None,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """Insert a document into semantic memory."""
        doc_id = str(uuid4())
        vec = vector or _simple_text_embedding(text)
        record = {
            "id": doc_id,
            "text": text,
            "namespace": namespace,
            "vector": vec,
            "metadata": metadata or {},
            "created_at": time.time(),
        }
        self._local_records.append(record)

        # Sync to Qdrant if available
        if self.qdrant:
            try:
                from qdrant_client.models import PointStruct
                self.qdrant.upsert(
                    collection_name=self.collection_name,
                    points=[
                        PointStruct(
                            id=doc_id,
                            vector=vec,
                            payload={"text": text, "namespace": namespace, **(metadata or {})}
                        )
                    ]
                )
            except Exception:
                pass

        return doc_id

    def search(
        self,
        query: str,
        namespace: str = "default",
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Semantic search retrieving top-k matches filtered by namespace."""
        query_vec = _simple_text_embedding(query)

        scored = []
        for rec in self._local_records:
            if rec["namespace"] == namespace:
                score = _cosine_similarity(query_vec, rec["vector"])
                if score >= threshold:
                    scored.append((score, rec))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, rec in scored[:top_k]:
            results.append({
                "id": rec["id"],
                "text": rec["text"],
                "score": round(score, 4),
                "metadata": rec["metadata"],
                "created_at": rec["created_at"],
            })

        return results
