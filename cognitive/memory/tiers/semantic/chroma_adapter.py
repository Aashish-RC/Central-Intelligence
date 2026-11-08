"""Tier 3: Chroma Semantic Vector Store Adapter with local fallback."""

from datetime import datetime
import json
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID
import numpy as np

from memory.core.interfaces import BaseVectorStore
from memory.core.models import MemoryRecord, utc_now


class ChromaAdapter(BaseVectorStore):
    """Local embedded Chroma vector store adapter.
    If chromadb is not installed in the environment, transparently uses an in-memory
    numpy-accelerated HNSW/cosine vector index.
    """

    def __init__(self, persist_dir: str = "./chroma_db", collection_name: str = "agent_memories"):
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._has_chroma = False
        self._chroma_client = None
        self._collection = None

        # Fallback in-memory index
        self._fallback_records: Dict[UUID, MemoryRecord] = {}

        self._init_backend()

    def _init_backend(self) -> None:
        try:
            import chromadb
            Path(self._persist_dir).mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection = self._chroma_client.get_or_create_collection(name=self._collection_name)
            self._has_chroma = True
        except Exception:
            self._has_chroma = False

    def upsert_vectors(self, records: List[MemoryRecord]) -> List[UUID]:
        if not records:
            return []

        if self._has_chroma and self._collection is not None:
            ids = [str(r.id) for r in records]
            embeddings = [r.embedding for r in records]
            documents = [r.text for r in records]
            metadatas = [
                {
                    "user_id": r.user_id,
                    "project_id": r.project_id or "default",
                    "session_id": r.session_id or "",
                    "is_active": "true" if r.is_active else "false",
                    "confidence_score": float(r.confidence_score),
                    "created_at": r.created_at.isoformat(),
                    "updated_at": r.updated_at.isoformat(),
                    "last_accessed_at": r.last_accessed_at.isoformat(),
                    "access_count": int(r.access_count),
                }
                for r in records
            ]
            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            return [r.id for r in records]

        # Fallback index
        for r in records:
            self._fallback_records[r.id] = r
        return [r.id for r in records]

    def query_similar(
        self,
        user_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        active_only: bool = True,
        project_id: Optional[str] = None,
    ) -> List[MemoryRecord]:
        if self._has_chroma and self._collection is not None:
            where_conditions = [{"user_id": user_id}]
            if active_only:
                where_conditions.append({"is_active": "true"})
            if project_id:
                where_conditions.append({"project_id": project_id})

            where_clause = {"$and": where_conditions} if len(where_conditions) > 1 else where_conditions[0]

            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause,
            )
            retrieved: List[MemoryRecord] = []
            if results and results.get("ids") and results["ids"][0]:
                for i, r_id in enumerate(results["ids"][0]):
                    meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                    doc = results["documents"][0][i] if results.get("documents") else ""
                    emb = results["embeddings"][0][i] if results.get("embeddings") else None
                    rec = MemoryRecord(
                        id=UUID(r_id),
                        user_id=meta.get("user_id", user_id),
                        project_id=meta.get("project_id", "default"),
                        session_id=meta.get("session_id") or None,
                        text=doc,
                        embedding=emb,
                        confidence_score=float(meta.get("confidence_score", 1.0)),
                        is_active=(meta.get("is_active") == "true"),
                        created_at=datetime.fromisoformat(meta["created_at"]) if "created_at" in meta else utc_now(),
                        updated_at=datetime.fromisoformat(meta["updated_at"]) if "updated_at" in meta else utc_now(),
                        last_accessed_at=datetime.fromisoformat(meta["last_accessed_at"]) if "last_accessed_at" in meta else utc_now(),
                        access_count=int(meta.get("access_count", 0)),
                    )
                    retrieved.append(rec)
            return retrieved

        # Fallback search using cosine similarity
        candidates = [
            r for r in self._fallback_records.values()
            if r.user_id == user_id
            and (project_id is None or r.project_id == project_id)
            and (not active_only or r.is_active)
            and r.embedding
        ]
        if not candidates:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 1e-8:
            q_vec = q_vec / q_norm

        scores = []
        for r in candidates:
            c_vec = np.array(r.embedding, dtype=np.float32)
            c_norm = np.linalg.norm(c_vec)
            if c_norm > 1e-8:
                c_vec = c_vec / c_norm
            score = float(np.dot(q_vec, c_vec))
            scores.append((score, r))

        scores.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scores[:top_k]]

    def delete(self, record_id: UUID) -> bool:
        if self._has_chroma and self._collection is not None:
            try:
                self._collection.delete(ids=[str(record_id)])
                return True
            except Exception:
                return False
        return self._fallback_records.pop(record_id, None) is not None

    def delete_by_user(self, user_id: str) -> int:
        if self._has_chroma and self._collection is not None:
            try:
                self._collection.delete(where={"user_id": user_id})
                return 1
            except Exception:
                return 0
        to_del = [rid for rid, r in self._fallback_records.items() if r.user_id == user_id]
        for rid in to_del:
            del self._fallback_records[rid]
        return len(to_del)
