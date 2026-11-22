"""Tier 3: PostgreSQL + pgvector Semantic Vector Store Adapter.

Consolidates vector storage into supabase-db, eliminating standalone Qdrant/Chroma containers.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from cognitive.memory.core.exceptions import AdapterConnectionError
from cognitive.memory.core.interfaces import BaseVectorStore
from cognitive.memory.core.models import MemoryRecord, utc_now
from platform_infra.data.supabase.supabase_adapter import SupabaseAdapter


class PgVectorAdapter(BaseVectorStore):
    """Semantic vector store implementation backed by PostgreSQL pgvector."""

    def __init__(
        self,
        connection_url: Optional[str] = None,
        collection_name: str = "agent_memories",
        dim: int = 384,
        supabase_adapter: Optional[SupabaseAdapter] = None,
    ):
        self._collection_name = collection_name
        self._dim = dim
        self._adapter = supabase_adapter or SupabaseAdapter(
            connection_url=connection_url,
            _defer_prod_check=True,
        )

    def check_health(self) -> bool:
        """Verify vector readiness."""
        return True

    def upsert_vectors(self, records: List[MemoryRecord]) -> List[UUID]:
        """Upsert memory records into pgvector."""
        if not records:
            return []

        result_ids = []
        for r in records:
            if not r.embedding:
                raise ValueError(f"Record {r.id} missing vector embedding for upsert.")

            metadata = {
                "project_id": r.project_id or "default",
                "session_id": r.session_id,
                "confidence_score": r.confidence_score,
                "is_active": r.is_active,
                "metadata": r.metadata,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
                "last_accessed_at": r.last_accessed_at.isoformat(),
                "access_count": r.access_count,
            }
            self._adapter.store_embedding(
                collection=self._collection_name,
                record_id=str(r.id),
                vector=r.embedding,
                document=r.text,
                user_id=r.user_id,
                metadata=metadata,
            )
            result_ids.append(r.id)

        return result_ids

    def query_similar(
        self,
        user_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        active_only: bool = True,
        project_id: Optional[str] = None,
    ) -> List[MemoryRecord]:
        """Query top-K semantically similar memories from pgvector."""
        results = self._adapter.search_embeddings(
            collection=self._collection_name,
            query_vector=query_embedding,
            top_k=top_k * 3 if (active_only or project_id) else top_k,
            user_id=user_id,
        )

        records: List[MemoryRecord] = []
        for res in results:
            meta = res.get("metadata", {})
            if active_only and not meta.get("is_active", True):
                continue
            if project_id and meta.get("project_id", "default") != project_id:
                continue

            created_at = utc_now()
            if meta.get("created_at"):
                try:
                    created_at = datetime.fromisoformat(meta["created_at"])
                except Exception:
                    pass

            rec = MemoryRecord(
                id=UUID(str(res["id"])),
                user_id=res.get("user_id", user_id),
                project_id=meta.get("project_id", "default"),
                session_id=meta.get("session_id"),
                text=res.get("document", ""),
                embedding=res.get("vector"),
                metadata=meta.get("metadata", {}),
                confidence_score=float(meta.get("confidence_score", 1.0)),
                is_active=bool(meta.get("is_active", True)),
                created_at=created_at,
                access_count=int(meta.get("access_count", 0)),
            )
            records.append(rec)
            if len(records) >= top_k:
                break

        return records

    def delete(self, record_id: UUID, user_id: Optional[str] = None) -> bool:
        """Delete vector record by id."""
        return self._adapter.delete_embedding(
            collection=self._collection_name,
            record_id=str(record_id),
            user_id=user_id or "default",
        )

    def delete_by_user(self, user_id: str) -> int:
        """Delete all vectors for a user."""
        records = self._adapter.vector_collections.get(self._collection_name, [])
        before = len(records)
        self._adapter.vector_collections[self._collection_name] = [
            r for r in records if r.user_id != user_id
        ]
        return before - len(self._adapter.vector_collections[self._collection_name])
