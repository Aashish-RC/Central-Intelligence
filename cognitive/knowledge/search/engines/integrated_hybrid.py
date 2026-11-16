"""Integrated Live Hybrid Retrieval Engine (Qdrant + pgvector + Apache AGE).

Orchestrates an integrated retrieval pipeline across all 3 live backends:
1. Qdrant: Dense approximate nearest-neighbor vector similarity.
2. PostgreSQL + pgvector: Persistent relational vector retrieval with ACID guarantees.
3. Apache AGE: Knowledge graph entity and relationship traversal via OpenCypher.

Fuses multi-modal candidate rankings using Reciprocal Rank Fusion (RRF),
enriches document hits with discovered graph relationships, enforces strict
tenant-scoping across every backend, and preserves provenance.
"""

from __future__ import annotations

import json
import math
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from cognitive.memory.core.interfaces import BaseEmbedder
from cognitive.memory.core.models import MemoryRecord, utc_now
from cognitive.memory.embeddings.embedder import get_embedder
from cognitive.memory.tiers.graph.age_adapter import ApacheAGEAdapter
from cognitive.memory.tiers.semantic.qdrant_adapter import QdrantAdapter
from platform_infra.data.supabase.supabase_adapter import SupabaseAdapter

from ..core.interfaces import BaseSearchEngine
from ..core.models import (
    CorpusType,
    SearchDocument,
    SearchQuery,
    SearchResponse,
    SearchResult,
)


class RetrievalBackendError(RuntimeError):
    """Raised when a mandatory retrieval backend fails or is unreachable in strict mode."""

    def __init__(self, backend: str, message: str, cause: Optional[Exception] = None) -> None:
        super().__init__(f"Retrieval backend [{backend}] failed: {message}")
        self.backend = backend
        self.cause = cause


def _doc_id_to_uuid(doc_id: str) -> uuid.UUID:
    """Deterministically convert an arbitrary document ID string to a valid UUIDv5."""
    try:
        return uuid.UUID(doc_id)
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(doc_id))


class IntegratedRetrievalResponse(SearchResponse):
    """Extended search response with multi-backend provenance and graph context."""

    backend_contributions: Dict[str, int]
    graph_entities: List[Dict[str, Any]]
    provenance_map: Dict[str, List[str]]
    execution_time_ms: float
    degraded: bool = False


class IntegratedHybridRetrievalEngine(BaseSearchEngine):
    """Production-grade hybrid retrieval engine combining Qdrant, pgvector, and Apache AGE."""

    def __init__(
        self,
        qdrant_adapter: Optional[QdrantAdapter] = None,
        age_adapter: Optional[ApacheAGEAdapter] = None,
        pgvector_adapter: Optional[SupabaseAdapter] = None,
        rrf_k: int = 60,
        weights: Tuple[float, float, float] = (0.40, 0.40, 0.20),
        strict_backends: bool = True,
        collection_name: str = "integrated_hybrid_kb",
        embedder: Optional[BaseEmbedder] = None,
        tenant_authorizer: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self.qdrant = qdrant_adapter
        self.age = age_adapter
        self.pgvector = pgvector_adapter
        self.rrf_k = rrf_k
        self.weights = weights  # (w_qdrant, w_pgvector, w_age)
        self.strict_backends = strict_backends
        self.collection_name = collection_name
        self.tenant_authorizer = tenant_authorizer
        if embedder is not None:
            self.embedder = embedder
        else:
            try:
                self.embedder = get_embedder()
            except Exception:
                self.embedder = None

    def _validate_tenant_authorization(
        self, caller_tenant: Optional[str], query_tenant: Optional[str] = None
    ) -> str:
        """Verify tenant context is established by a trusted caller or boundary."""
        effective_tenant = caller_tenant or query_tenant
        if not effective_tenant or not isinstance(effective_tenant, str) or not effective_tenant.strip():
            raise PermissionError("Tenant authorization failed: missing or empty tenant_id")

        effective_tenant = effective_tenant.strip()

        # Reject wildcard or injection characters in tenant_id
        if any(c in effective_tenant for c in ("*", "?", ";", "'", "\"", "\0", "\\", "/", "\n", "\r")):
            raise PermissionError(f"Tenant authorization failed: invalid tenant identifier '{effective_tenant}'")

        # If both caller context and query context are provided, ensure they strictly match
        if caller_tenant and query_tenant:
            c_t = caller_tenant.strip()
            q_t = query_tenant.strip()
            if c_t != q_t:
                raise PermissionError(
                    f"Tenant authorization mismatch: caller authorization context '{c_t}' "
                    f"does not match requested query tenant '{q_t}'"
                )

        # If an explicit authorizer callback is provided, invoke it
        if self.tenant_authorizer is not None:
            if not self.tenant_authorizer(effective_tenant):
                raise PermissionError(f"Tenant authorization failed: authorizer rejected tenant '{effective_tenant}'")

        return effective_tenant

    def index_document(
        self,
        document: SearchDocument,
        embedding: Optional[List[float]] = None,
        graph_entities: Optional[List[Dict[str, Any]]] = None,
        graph_relationships: Optional[List[Tuple[str, str, str]]] = None,
    ) -> None:
        """Index a document across Qdrant, pgvector, and Apache AGE with compensating cleanup on partial failure."""
        vec = embedding or document.embedding
        if not vec:
            if self.embedder is not None and (document.title or document.content):
                vec = self.embedder.embed_text(f"{document.title}\n{document.content}")
            else:
                raise ValueError(f"Document {document.id} requires an embedding vector for hybrid indexing.")

        tenant = self._validate_tenant_authorization(document.tenant_id)
        now = utc_now()
        indexed_backends: List[str] = []

        # 1. Index into Qdrant vector store
        if self.qdrant:
            try:
                rec_uuid = _doc_id_to_uuid(document.id)
                rec = MemoryRecord(
                    id=rec_uuid,
                    user_id=tenant,
                    project_id=document.project_id,
                    text=f"{document.title}\n{document.content}",
                    embedding=vec,
                    metadata={
                        "doc_id": document.id,
                        "title": document.title,
                        "corpus_type": document.corpus_type.value,
                        "tags": document.tags,
                        "tenant_id": tenant,
                        "project_id": document.project_id,
                        "custom": document.metadata,
                    },
                    confidence_score=1.0,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                    last_accessed_at=now,
                )
                self.qdrant.upsert_vectors([rec])
                indexed_backends.append("qdrant")
            except Exception as exc:
                if self.strict_backends:
                    raise RetrievalBackendError("qdrant", f"Failed to index into Qdrant: {exc}", cause=exc)

        # 2. Index into pgvector persistent relational store
        if self.pgvector:
            try:
                col_name = f"pgvec_{self.collection_name}"
                self.pgvector.store_embedding(
                    collection=col_name,
                    record_id=document.id,
                    vector=vec,
                    document=f"{document.title}\n{document.content}",
                    user_id=tenant,
                    metadata={
                        "doc_id": document.id,
                        "title": document.title,
                        "corpus_type": document.corpus_type.value,
                        "tags": document.tags,
                        "tenant_id": tenant,
                        "project_id": document.project_id,
                        "custom": document.metadata,
                    },
                )
                indexed_backends.append("pgvector")
            except Exception as exc:
                if self.strict_backends:
                    # Compensating rollback: delete from Qdrant
                    if "qdrant" in indexed_backends and self.qdrant:
                        try:
                            self.qdrant.delete(_doc_id_to_uuid(document.id))
                        except Exception:
                            pass
                    raise RetrievalBackendError("pgvector", f"Failed to index into pgvector: {exc}", cause=exc)

        # 3. Index entities and relationships into Apache AGE graph
        if self.age:
            try:
                # Add Document root node
                self.age.add_entity(
                    user_id=tenant,
                    name=document.id,
                    entity_type="Document",
                    properties={"title": document.title, "tenant_id": tenant, "doc_id": document.id},
                    project_id=document.project_id,
                )
                # Add auxiliary graph entities
                if graph_entities:
                    for ent in graph_entities:
                        name = ent.get("name")
                        if name:
                            self.age.add_entity(
                                user_id=tenant,
                                name=name,
                                entity_type=ent.get("label") or ent.get("entity_type", "Entity"),
                                properties=ent.get("properties", {}),
                                project_id=document.project_id,
                            )
                # Add graph edges / relationships
                if graph_relationships:
                    for src, rel, tgt in graph_relationships:
                        self.age.add_relationship(
                            user_id=tenant,
                            source=src,
                            relation=rel,
                            target=tgt,
                            properties={"doc_id": document.id, "tenant_id": tenant},
                            project_id=document.project_id,
                        )
                indexed_backends.append("apache_age")
            except Exception as exc:
                if self.strict_backends:
                    # Compensating rollback: delete from pgvector and Qdrant
                    if "pgvector" in indexed_backends and self.pgvector:
                        try:
                            self.pgvector.delete_embedding(
                                f"pgvec_{self.collection_name}", document.id, user_id=tenant
                            )
                        except Exception:
                            pass
                    if "qdrant" in indexed_backends and self.qdrant:
                        try:
                            self.qdrant.delete(_doc_id_to_uuid(document.id))
                        except Exception:
                            pass
                    raise RetrievalBackendError("apache_age", f"Failed to index into Apache AGE: {exc}", cause=exc)

    def index_batch(self, docs: List[SearchDocument]) -> int:
        """Upsert a batch of search documents."""
        count = 0
        for doc in docs:
            self.index_document(doc)
            count += 1
        return count

    def delete_document(self, doc_id: str, tenant_id: Optional[str] = None) -> bool:
        """Delete a document by its composite ID across Qdrant, pgvector, and Apache AGE."""
        if not doc_id:
            return False

        qdrant_deleted = False
        pg_deleted = False
        age_deleted = False

        if self.qdrant:
            try:
                rec_uuid = _doc_id_to_uuid(doc_id)
                qdrant_deleted = self.qdrant.delete(rec_uuid)
            except Exception:
                pass

        if self.pgvector:
            try:
                col_name = f"pgvec_{self.collection_name}"
                pg_deleted = self.pgvector.delete_embedding(
                    collection=col_name,
                    record_id=doc_id,
                    user_id=tenant_id,
                )
            except Exception:
                pass

        if self.age:
            try:
                cypher = (
                    "MATCH (n) WHERE (n.name = $name OR n.doc_id = $name) "
                    "AND ($tenant IS NULL OR n.user_id = $tenant) "
                    "DETACH DELETE n RETURN count(*) AS deleted"
                )
                rows = self.age.execute_query(
                    cypher,
                    params={"name": doc_id, "tenant": tenant_id},
                )
                if rows:
                    age_deleted = True
                cypher_edge = (
                    "MATCH ()-[r]->() WHERE r.doc_id = $name "
                    "AND ($tenant IS NULL OR r.tenant_id = $tenant) "
                    "DELETE r"
                )
                self.age.execute_query(
                    cypher_edge,
                    params={"name": doc_id, "tenant": tenant_id},
                )
            except Exception:
                pass

        return qdrant_deleted or pg_deleted or age_deleted

    def delete_by_project(self, project_id: str, tenant_id: Optional[str] = None) -> int:
        """Purge all indexed documents belonging to a project across all backends."""
        if not project_id:
            return 0
        total_deleted = 0
        if self.qdrant and hasattr(self.qdrant, "delete_by_project"):
            try:
                total_deleted += self.qdrant.delete_by_project(project_id=project_id, user_id=tenant_id)
            except Exception:
                pass

        if self.pgvector and hasattr(self.pgvector, "delete_by_project"):
            try:
                col_name = f"pgvec_{self.collection_name}"
                total_deleted += self.pgvector.delete_by_project(
                    collection=col_name,
                    project_id=project_id,
                    user_id=tenant_id,
                )
            except Exception:
                pass

        if self.age and hasattr(self.age, "delete_by_project"):
            try:
                total_deleted += self.age.delete_by_project(project_id=project_id, user_id=tenant_id)
            except Exception:
                pass

        return total_deleted

    def retrieve(
        self,
        query: Union[str, SearchQuery],
        tenant_id: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 10,
        weights: Optional[Tuple[float, float, float]] = None,
        project_id: str = "default",
    ) -> IntegratedRetrievalResponse:
        """Execute unified 3-backend retrieval across Qdrant, pgvector, and Apache AGE.

        Workflow:
        1. Tenant boundaries are enforced across all queries.
        2. Top-K candidates are queried from Qdrant.
        3. Top-K candidates are queried from pgvector.
        4. Related graph entities and relationships are traversed in Apache AGE.
        5. Candidates are deduplicated and normalized into SearchDocument records.
        6. Graph relationships are enriched into candidate metadata.
        7. Multi-source Reciprocal Rank Fusion (RRF) produces calibrated ranking.
        8. Comprehensive provenance and backend contribution metrics are generated.
        """
        start_time = time.perf_counter()
        q_text = query.query_text if isinstance(query, SearchQuery) else str(query)
        req_tenant = query.tenant_id if isinstance(query, SearchQuery) else None
        q_tenant = self._validate_tenant_authorization(tenant_id, req_tenant)
        q_proj = project_id or (query.project_id if isinstance(query, SearchQuery) else "default")
        eff_weights = weights or self.weights

        # Auto-compute query embedding using established embedder if not explicitly provided
        effective_embedding = query_embedding
        if effective_embedding is None and self.embedder is not None and q_text:
            try:
                effective_embedding = self.embedder.embed_text(q_text)
            except Exception:
                effective_embedding = None

        w_qdrant, w_pgvector, w_age = eff_weights

        qdrant_candidates: List[Tuple[str, SearchDocument, float]] = []
        pgvector_candidates: List[Tuple[str, SearchDocument, float]] = []
        age_candidates: List[Tuple[str, SearchDocument, float]] = []
        graph_relationships_found: List[Dict[str, Any]] = []
        failed_backends: List[str] = []

        # -------------------------------------------------------------
        # 1. Qdrant Vector Retrieval
        # -------------------------------------------------------------
        if self.qdrant and effective_embedding is not None:
            try:
                hits = self.qdrant.query_similar(
                    user_id=q_tenant,
                    query_embedding=effective_embedding,
                    top_k=top_k * 2,
                    active_only=True,
                )
                for rec in hits:
                    doc_id = rec.metadata.get("doc_id", str(rec.id))
                    title = rec.metadata.get("title", "")
                    content = rec.text
                    if title and content.startswith(title + "\n"):
                        content = content[len(title) + 1 :]
                    c_type = rec.metadata.get("corpus_type", CorpusType.FILE.value)
                    doc = SearchDocument(
                        id=doc_id,
                        title=title or doc_id,
                        content=content,
                        tenant_id=q_tenant,
                        project_id=rec.project_id or q_proj,
                        corpus_type=CorpusType(c_type) if c_type in CorpusType._value2member_map_ else CorpusType.FILE,
                        tags=rec.metadata.get("tags", []),
                        metadata=rec.metadata.get("custom", {}),
                        embedding=rec.embedding,
                    )
                    qdrant_candidates.append((doc_id, doc, float(rec.confidence_score)))
            except Exception as exc:
                if self.strict_backends:
                    raise RetrievalBackendError("qdrant", str(exc), cause=exc)
                failed_backends.append("qdrant")

        # -------------------------------------------------------------
        # 2. pgvector Relational Embedding Retrieval
        # -------------------------------------------------------------
        if self.pgvector and effective_embedding is not None:
            try:
                col_name = f"pgvec_{self.collection_name}"
                pg_hits = self.pgvector.search_embeddings(
                    collection=col_name,
                    query_vector=effective_embedding,
                    top_k=top_k * 2,
                    user_id=q_tenant,
                )
                for r in pg_hits:
                    doc_id = str(r["id"])
                    meta = r.get("metadata", {})
                    title = meta.get("title", "")
                    content = r.get("document", "")
                    if title and content.startswith(title + "\n"):
                        content = content[len(title) + 1 :]
                    c_type = meta.get("corpus_type", CorpusType.FILE.value)
                    doc = SearchDocument(
                        id=doc_id,
                        title=title or doc_id,
                        content=content,
                        tenant_id=q_tenant,
                        project_id=meta.get("project_id", q_proj),
                        corpus_type=CorpusType(c_type) if c_type in CorpusType._value2member_map_ else CorpusType.FILE,
                        tags=meta.get("tags", []),
                        metadata=meta.get("custom", {}),
                    )
                    pgvector_candidates.append((doc_id, doc, float(r.get("similarity", 1.0))))
            except Exception as exc:
                if self.strict_backends:
                    raise RetrievalBackendError("pgvector", str(exc), cause=exc)
                failed_backends.append("pgvector")

        # -------------------------------------------------------------
        # 3. Apache AGE Graph Traversal & Relationship Retrieval
        # -------------------------------------------------------------
        if self.age:
            try:
                # Query related graph edges where BOTH source and target vertices belong strictly to this tenant
                cypher = (
                    "MATCH (a)-[r]->(b) "
                    "WHERE a.user_id = $tenant AND b.user_id = $tenant "
                    "RETURN a.name AS source, type(r) AS relation, b.name AS target, "
                    "a.props_json AS a_props, b.props_json AS b_props"
                )
                edges = self.age.execute_query(cypher, params={"tenant": q_tenant})
                graph_relationships_found.extend(edges)

                # Associate traversed entities with target documents
                for edge in edges:
                    src = edge.get("source")
                    tgt = edge.get("target")
                    rel = edge.get("relation")
                    a_props = {}
                    b_props = {}
                    if edge.get("a_props"):
                        try:
                            a_props = json.loads(edge["a_props"]) if isinstance(edge["a_props"], str) else edge["a_props"]
                        except Exception:
                            pass
                    if edge.get("b_props"):
                        try:
                            b_props = json.loads(edge["b_props"]) if isinstance(edge["b_props"], str) else edge["b_props"]
                        except Exception:
                            pass

                    # Check if source or target represents a document ID
                    target_doc_id = a_props.get("doc_id") or b_props.get("doc_id") or src or tgt
                    keywords = re.findall(r"[A-Za-z0-9_]+", q_text.lower())
                    match_score = 0.5
                    for kw in keywords:
                        if kw in str(src).lower() or kw in str(tgt).lower() or kw in str(rel).lower():
                            match_score += 0.5

                    doc = SearchDocument(
                        id=target_doc_id,
                        title=a_props.get("title") or b_props.get("title") or f"Graph Entity {target_doc_id}",
                        content=f"Knowledge Graph Connection: {src} --[{rel}]--> {tgt}",
                        tenant_id=q_tenant,
                        project_id=q_proj,
                        corpus_type=CorpusType.NOTE,
                        metadata={"graph_edge": {"source": src, "relation": rel, "target": tgt}},
                    )
                    age_candidates.append((target_doc_id, doc, match_score))
            except Exception as exc:
                if self.strict_backends:
                    raise RetrievalBackendError("apache_age", str(exc), cause=exc)
                failed_backends.append("apache_age")

        # -------------------------------------------------------------
        # 4. Deduplication & Provenance Tracking
        # -------------------------------------------------------------
        doc_registry: Dict[str, SearchDocument] = {}
        provenance_map: Dict[str, Set[str]] = {}
        qdrant_ranks: Dict[str, int] = {}
        pgvector_ranks: Dict[str, int] = {}
        age_ranks: Dict[str, int] = {}

        # 1-based ranks
        for rank, (did, doc, _) in enumerate(qdrant_candidates, 1):
            doc_registry[did] = doc
            provenance_map.setdefault(did, set()).add("qdrant")
            if did not in qdrant_ranks:
                qdrant_ranks[did] = rank

        for rank, (did, doc, _) in enumerate(pgvector_candidates, 1):
            if did not in doc_registry:
                doc_registry[did] = doc
            provenance_map.setdefault(did, set()).add("pgvector")
            if did not in pgvector_ranks:
                pgvector_ranks[did] = rank

        for rank, (did, doc, _) in enumerate(age_candidates, 1):
            if did not in doc_registry:
                doc_registry[did] = doc
            provenance_map.setdefault(did, set()).add("apache_age")
            if did not in age_ranks:
                age_ranks[did] = rank

        # -------------------------------------------------------------
        # 5. Multi-Source Reciprocal Rank Fusion (RRF) Calculation
        # -------------------------------------------------------------
        fused_scores: Dict[str, float] = {}
        k_val = self.rrf_k

        all_doc_ids = set(doc_registry.keys())
        for did in all_doc_ids:
            score = 0.0
            if did in qdrant_ranks:
                score += w_qdrant * (1.0 / (k_val + qdrant_ranks[did]))
            if did in pgvector_ranks:
                score += w_pgvector * (1.0 / (k_val + pgvector_ranks[did]))
            if did in age_ranks:
                score += w_age * (1.0 / (k_val + age_ranks[did]))
            fused_scores[did] = score

        # Sort descending by fused RRF score with stable tie-breaking on doc_id
        sorted_ids = sorted(all_doc_ids, key=lambda did: (-fused_scores[did], str(did)))[:top_k]

        # -------------------------------------------------------------
        # 6. Graph Enrichment & Result Assembly
        # -------------------------------------------------------------
        results: List[SearchResult] = []
        for did in sorted_ids:
            doc = doc_registry[did]
            # Attach graph relationships discovered for this document (exact match)
            doc_graph_links = []
            for e in graph_relationships_found:
                src = e.get("source")
                tgt = e.get("target")
                a_props = e.get("a_props") or {}
                b_props = e.get("b_props") or {}
                if isinstance(a_props, str):
                    try:
                        a_props = json.loads(a_props)
                    except Exception:
                        a_props = {}
                if isinstance(b_props, str):
                    try:
                        b_props = json.loads(b_props)
                    except Exception:
                        b_props = {}
                if (
                    src == did
                    or tgt == did
                    or a_props.get("doc_id") == did
                    or b_props.get("doc_id") == did
                ):
                    doc_graph_links.append(e)

            enriched_meta = dict(doc.metadata)
            enriched_meta["provenance"] = sorted(list(provenance_map.get(did, [])))
            if doc_graph_links:
                enriched_meta["graph_enrichment"] = doc_graph_links

            enriched_doc = doc.model_copy(update={"metadata": enriched_meta})

            results.append(
                SearchResult(
                    document=enriched_doc,
                    rrf_score=round(fused_scores[did], 6),
                    vector_rank=qdrant_ranks.get(did),
                    graph_rank=age_ranks.get(did),
                    highlights=[enriched_doc.content[:150] + "..."] if len(enriched_doc.content) > 150 else [enriched_doc.content],
                )
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Report accurate backend contributions, flagging failed backends in degraded mode
        backend_counts = {
            "qdrant": len(qdrant_candidates) if "qdrant" not in failed_backends else -1,
            "pgvector": len(pgvector_candidates) if "pgvector" not in failed_backends else -1,
            "apache_age": len(age_candidates) if "apache_age" not in failed_backends else -1,
        }

        serializable_prov = {did: sorted(list(prov)) for did, prov in provenance_map.items()}

        return IntegratedRetrievalResponse(
            query=q_text,
            tenant_id=q_tenant,
            project_id=q_proj,
            total_hits=len(results),
            results=results,
            backend_contributions=backend_counts,
            graph_entities=graph_relationships_found,
            provenance_map=serializable_prov,
            execution_time_ms=round(duration_ms, 2),
            degraded=len(failed_backends) > 0,
        )

    def search(self, query: SearchQuery) -> SearchResponse:
        """BaseSearchEngine interface compatibility, leveraging vector and graph retrieval."""
        vec = getattr(query, "embedding", None)
        if vec is None and self.embedder is not None and query.query_text:
            try:
                vec = self.embedder.embed_text(query.query_text)
            except Exception:
                vec = None

        res = self.retrieve(
            query=query,
            tenant_id=query.tenant_id,
            query_embedding=vec,
            top_k=query.limit,
            project_id=query.project_id,
        )
        return SearchResponse(
            query=res.query,
            tenant_id=res.tenant_id,
            project_id=res.project_id,
            total_hits=res.total_hits,
            results=res.results,
        )
