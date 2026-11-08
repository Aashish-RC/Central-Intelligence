"""Tier 3: Qdrant Semantic Vector Store Adapter supporting payload filtering."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    PointIdsList,
)

from memory.core.interfaces import BaseVectorStore
from memory.core.models import MemoryRecord, utc_now
from memory.core.exceptions import AdapterConnectionError


class QdrantAdapter(BaseVectorStore):
    """Production & local vector storage powered by Qdrant engine.
    Supports payload filters on user_id, is_active, and temporal attributes.
    """

    def __init__(
        self,
        location: str = ":memory:",
        collection_name: str = "agent_memories",
        dim: int = 384,
        distance: Distance = Distance.COSINE,
    ):
        self._location = location
        self._collection_name = collection_name
        self._dim = dim
        self._distance = distance
        self._client: Optional[QdrantClient] = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            if self._location == ":memory:":
                self._client = QdrantClient(":memory:")
            elif self._location.startswith("http://") or self._location.startswith("https://"):
                self._client = QdrantClient(url=self._location)
            else:
                self._client = QdrantClient(path=self._location)

            # Ensure collection exists
            collections = self._client.get_collections().collections
            exists = any(c.name == self._collection_name for c in collections)
            if not exists:
                self._client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=VectorParams(size=self._dim, distance=self._distance),
                )
        except Exception as e:
            raise AdapterConnectionError(f"Failed to initialize Qdrant at '{self._location}': {e}")

    def check_health(self) -> bool:
        """Verify connection and collection readiness."""
        try:
            if not self._client:
                return False
            collections = self._client.get_collections().collections
            return any(c.name == self._collection_name for c in collections)
        except Exception:
            return False

    def upsert_vectors(self, records: List[MemoryRecord]) -> List[UUID]:
        if not records:
            return []

        points = []
        result_ids = []
        for r in records:
            if not r.embedding:
                raise ValueError(f"Record {r.id} missing vector embedding for upsert.")

            payload = {
                "user_id": r.user_id,
                "project_id": r.project_id or "default",
                "session_id": r.session_id,
                "text": r.text,
                "metadata": r.metadata,
                "confidence_score": r.confidence_score,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
                "last_accessed_at": r.last_accessed_at.isoformat(),
                "access_count": r.access_count,
            }
            points.append(PointStruct(id=str(r.id), vector=r.embedding, payload=payload))
            result_ids.append(r.id)

        self._client.upsert(collection_name=self._collection_name, points=points)
        return result_ids

    def query_similar(
        self,
        user_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        active_only: bool = True,
        project_id: Optional[str] = None,
    ) -> List[MemoryRecord]:
        must_conditions = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        if active_only:
            must_conditions.append(FieldCondition(key="is_active", match=MatchValue(value=True)))
        if project_id:
            must_conditions.append(FieldCondition(key="project_id", match=MatchValue(value=project_id)))

        query_filter = Filter(must=must_conditions)

        # Use query_points or fallback to search
        try:
            res = self._client.query_points(
                collection_name=self._collection_name,
                query=query_embedding,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
                with_vectors=True,
            )
            scored_points = res.points
        except (AttributeError, TypeError):
            scored_points = self._client.search(
                collection_name=self._collection_name,
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
                with_vectors=True,
            )

        records: List[MemoryRecord] = []
        for p in scored_points:
            payload = p.payload or {}
            rec = MemoryRecord(
                id=UUID(str(p.id)),
                user_id=payload.get("user_id", user_id),
                project_id=payload.get("project_id", "default"),
                session_id=payload.get("session_id"),
                text=payload.get("text", ""),
                embedding=p.vector if isinstance(p.vector, list) else None,
                metadata=payload.get("metadata", {}),
                confidence_score=float(payload.get("confidence_score", 1.0)),
                is_active=bool(payload.get("is_active", True)),
                created_at=datetime.fromisoformat(payload["created_at"]) if "created_at" in payload else utc_now(),
                updated_at=datetime.fromisoformat(payload["updated_at"]) if "updated_at" in payload else utc_now(),
                last_accessed_at=datetime.fromisoformat(payload["last_accessed_at"]) if "last_accessed_at" in payload else utc_now(),
                access_count=int(payload.get("access_count", 0)),
            )
            records.append(rec)

        return records

    def delete(self, record_id: UUID) -> bool:
        try:
            self._client.delete(
                collection_name=self._collection_name,
                points_selector=PointIdsList(points=[str(record_id)]),
            )
            return True
        except Exception:
            return False

    def delete_by_user(self, user_id: str) -> int:
        filt = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
        try:
            self._client.delete(collection_name=self._collection_name, points_selector=filt)
            return 1
        except Exception:
            return 0
