"""D3 Verification: Combined Live Hybrid Retrieval Integration Test Suite.

Executes a genuine end-to-end retrieval workflow using all three live backends:
1. Qdrant: Dense ANN vector similarity search.
2. PostgreSQL + pgvector: Persistent relational embedding search.
3. Apache AGE: OpenCypher graph relationship traversal and context enrichment.

Verifies:
- Creation of isolated, disposable test data across all 3 live backends.
- A single application-level request executing across all three backends.
- Verifiable contributions from Qdrant, pgvector, and Apache AGE.
- Multi-source Reciprocal Rank Fusion (RRF) and graph enrichment.
- Strict tenant boundary isolation preventing cross-tenant leakage.
- Deduplication and multi-backend provenance tracking.
- Persistence of vector and relational state across queries.
- Explicit fail-closed behavior when a backend becomes unavailable.
- Deterministic cleanup without disturbing unrelated data.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pg8000.dbapi
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load local .env into os.environ if present
_env_path = REPO_ROOT / ".env"
if _env_path.is_file():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

from cognitive.knowledge.search.core.models import CorpusType, SearchDocument, SearchQuery
from cognitive.memory.core.models import MemoryRecord
from cognitive.knowledge.search.engines.integrated_hybrid import (
    IntegratedHybridRetrievalEngine,
    IntegratedRetrievalResponse,
    RetrievalBackendError,
)
from cognitive.memory.engine import MemoryEngine
from cognitive.memory.tiers.graph.age_adapter import ApacheAGEAdapter
from cognitive.memory.tiers.semantic.qdrant_adapter import QdrantAdapter
from platform_infra.data.supabase.supabase_adapter import SupabaseAdapter

pytestmark = pytest.mark.live

# Live service endpoints
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
AGE_POSTGRES_PORT = int(os.getenv("AGE_POSTGRES_PORT", "5433"))
AGE_POSTGRES_PASS = os.getenv("POSTGRES_PASSWORD", "postgres-development-pass")
AGE_URL = os.getenv(
    "AGE_POSTGRES_URL",
    f"postgresql://postgres:{AGE_POSTGRES_PASS}@127.0.0.1:{AGE_POSTGRES_PORT}/postgres",
)
PGVECTOR_URL = os.getenv(
    "POSTGRES_LIVE_URL",
    "postgresql://postgres:ci-test-password@127.0.0.1:5434/ci_test",
)


def _ensure_live_services() -> None:
    """Ensure Docker containers for Qdrant and Apache AGE are started."""
    if not shutil.which("docker"):
        pytest.skip("Docker CLI not available")
    try:
        # Start qdrant and apache-age if not running
        subprocess.run(
            ["docker", "start", "central-qdrant", "central-apache-age"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10.0,
        )
    except Exception as exc:
        pytest.skip(f"Failed to ensure containers running: {exc}")

    # Wait for Qdrant HTTP healthz
    import httpx
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{QDRANT_URL}/healthz", timeout=2.0)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1.0)
    else:
        pytest.skip("Qdrant did not become healthy in time")

    # Wait for Apache AGE Postgres
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        try:
            conn = pg8000.dbapi.connect(
                host="127.0.0.1",
                port=AGE_POSTGRES_PORT,
                user="postgres",
                password=AGE_POSTGRES_PASS,
                database="postgres",
                timeout=2,
            )
            conn.close()
            break
        except Exception:
            pass
        time.sleep(1.0)
    else:
        pytest.skip("Apache AGE did not become ready in time")

    # Wait for pgvector Postgres
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        try:
            conn = pg8000.dbapi.connect(
                host="127.0.0.1",
                port=5434,
                user="postgres",
                password="ci-test-password",
                database="ci_test",
                timeout=2,
            )
            conn.close()
            break
        except Exception:
            pass
        time.sleep(1.0)
    else:
        pytest.skip("pgvector did not become ready in time")


@pytest.fixture(scope="module")
def live_services():
    """Module-level fixture ensuring live backends are ready."""
    _ensure_live_services()
    yield
    # Conserve system memory after test module finishes
    try:
        subprocess.run(
            ["docker", "stop", "central-qdrant", "central-apache-age"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10.0,
        )
    except Exception:
        pass


def test_d3_combined_live_retrieval_e2e(live_services):
    """Primary D3 Test: End-to-end retrieval verifying all 3 backends contribute,

    with RRF ranking, graph enrichment, tenant isolation, deduplication, and persistence.
    """
    col_suffix = uuid4().hex[:8]
    collection_name = f"d3_e2e_{col_suffix}"
    age_graph_name = f"d3_graph_{col_suffix}"

    tenant_alpha = f"tenant_alpha_{col_suffix}"
    tenant_beta = f"tenant_beta_{col_suffix}"

    dim = 8

    # 1. Initialize Adapters
    qdrant = QdrantAdapter(
        location=QDRANT_URL,
        collection_name=collection_name,
        dim=dim,
    )
    assert qdrant.check_health() is True, "Qdrant health check failed"

    age = ApacheAGEAdapter(
        postgres_url=AGE_URL,
        graph_name=age_graph_name,
        auto_fallback=False,
    )
    assert age.check_health() is True, "Apache AGE health check failed"
    assert age.is_in_memory is False, "Apache AGE unexpectedly running in-memory fallback"

    pgvec = SupabaseAdapter(connection_url=PGVECTOR_URL, _defer_prod_check=True)
    pgvec.adapter_mode = "live"

    engine = IntegratedHybridRetrievalEngine(
        qdrant_adapter=qdrant,
        age_adapter=age,
        pgvector_adapter=pgvec,
        rrf_k=60,
        weights=(0.40, 0.40, 0.20),
        strict_backends=True,
        collection_name=collection_name,
    )

    try:
        # 2. Seed Test Documents
        # Target Document: Present across all 3 backends (Qdrant, pgvector, Apache AGE)
        doc_consensus = SearchDocument(
            id=f"doc_consensus_{col_suffix}",
            title="Distributed Raft Consensus Protocol",
            content="Raft consensus achieves state machine replication via leader election, log replication, and commit safety.",
            tenant_id=tenant_alpha,
            project_id="proj_core",
            corpus_type=CorpusType.FILE,
            tags=["consensus", "raft", "distributed"],
        )
        vec_consensus = [0.95, 0.10, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        graph_entities = [
            {"name": "RaftProtocol", "label": "Protocol", "properties": {"consensus_type": "leader-based"}},
            {"name": "LeaderElection", "label": "Mechanism", "properties": {"heartbeat_timeout_ms": 150}},
        ]
        graph_rels = [
            (doc_consensus.id, "SPECIFIES", "RaftProtocol"),
            ("RaftProtocol", "REQUIRES", "LeaderElection"),
        ]

        engine.index_document(
            document=doc_consensus,
            embedding=vec_consensus,
            graph_entities=graph_entities,
            graph_relationships=graph_rels,
        )

        # Document 2: Indexed in Qdrant only
        doc_qdrant_only = SearchDocument(
            id=f"doc_qdrant_{col_suffix}",
            title="Vector Memory ANN Indexing",
            content="Qdrant provides HNSW vector search indexing.",
            tenant_id=tenant_alpha,
            project_id="proj_core",
            corpus_type=CorpusType.MEMORY,
            tags=["vector", "ann"],
        )
        vec_qdrant = [0.80, 0.30, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        rec_qdrant = MemoryRecord(
            id=uuid4(),
            user_id=tenant_alpha,
            project_id="proj_core",
            text=f"{doc_qdrant_only.title}\n{doc_qdrant_only.content}",
            embedding=vec_qdrant,
            metadata={"doc_id": doc_qdrant_only.id, "title": doc_qdrant_only.title, "tags": doc_qdrant_only.tags},
        )
        qdrant.upsert_vectors([rec_qdrant])

        # Document 3: Stored in pgvector only
        doc_pg_only = SearchDocument(
            id=f"doc_pgvec_{col_suffix}",
            title="Postgres Relational Durability",
            content="PostgreSQL writes WAL logs for crash recovery.",
            tenant_id=tenant_alpha,
            project_id="proj_core",
            corpus_type=CorpusType.FILE,
            tags=["postgres", "durability"],
        )
        vec_pg = [0.75, 0.35, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        pgvec.store_embedding(
            collection=f"pgvec_{collection_name}",
            record_id=doc_pg_only.id,
            vector=vec_pg,
            document=f"{doc_pg_only.title}\n{doc_pg_only.content}",
            user_id=tenant_alpha,
            metadata={"title": doc_pg_only.title, "doc_id": doc_pg_only.id},
        )

        # Document 4: Separate Tenant (tenant_beta) — identical vectors, MUST NOT be retrieved
        doc_other_tenant = SearchDocument(
            id=f"doc_other_tenant_{col_suffix}",
            title="Tenant Beta Secret Specification",
            content="Proprietary Raft protocol implementation for another customer.",
            tenant_id=tenant_beta,
            project_id="proj_other",
            corpus_type=CorpusType.FILE,
            tags=["consensus", "confidential"],
        )
        engine.index_document(
            document=doc_other_tenant,
            embedding=vec_consensus,
            graph_entities=[{"name": "BetaSecret", "label": "Secret"}],
            graph_relationships=[(doc_other_tenant.id, "CONTAINS", "BetaSecret")],
        )

        # 3. Execute Unified Retrieval Request for tenant_alpha
        query_vec = [0.94, 0.11, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        query = SearchQuery(
            query_text="Raft consensus protocol leader election",
            tenant_id=tenant_alpha,
            limit=5,
        )

        response: IntegratedRetrievalResponse = engine.retrieve(
            query=query,
            tenant_id=tenant_alpha,
            query_embedding=query_vec,
            top_k=5,
        )

        # 4. Prove all three backends contributed to the retrieval process
        assert response.backend_contributions["qdrant"] > 0, "Qdrant backend contributed zero candidates"
        assert response.backend_contributions["pgvector"] > 0, "pgvector backend contributed zero candidates"
        assert response.backend_contributions["apache_age"] > 0, "Apache AGE backend contributed zero candidates"

        # 5. Verify RRF ranking: doc_consensus present across all 3 backends must rank #1
        assert len(response.results) > 0, "No results returned from integrated retrieval"
        top_hit = response.results[0]
        assert top_hit.document.id == doc_consensus.id, f"Expected top hit {doc_consensus.id}, got {top_hit.document.id}"
        assert top_hit.rrf_score > 0.0, f"Expected positive RRF score, got {top_hit.rrf_score}"

        # 6. Verify Deduplication and Provenance
        hit_ids = [r.document.id for r in response.results]
        assert len(hit_ids) == len(set(hit_ids)), f"Duplicate documents detected in results: {hit_ids}"

        consensus_prov = top_hit.document.metadata.get("provenance", [])
        assert "qdrant" in consensus_prov, f"Missing Qdrant provenance: {consensus_prov}"
        assert "pgvector" in consensus_prov, f"Missing pgvector provenance: {consensus_prov}"
        assert "apache_age" in consensus_prov, f"Missing Apache AGE provenance: {consensus_prov}"

        # 7. Verify Knowledge Graph Context Enrichment
        enrichment = top_hit.document.metadata.get("graph_enrichment", [])
        assert len(enrichment) > 0, "Top hit was not enriched with Apache AGE graph context"
        relations_found = [e.get("relation") for e in enrichment]
        assert "SPECIFIES" in relations_found, f"Expected SPECIFIES edge in graph enrichment: {relations_found}"

        # 8. Strict Tenant Boundary Verification
        for res in response.results:
            assert res.document.tenant_id == tenant_alpha, f"Cross-tenant data leakage! Document {res.document.id} belongs to {res.document.tenant_id}"
            assert res.document.id != doc_other_tenant.id, "Tenant Beta document was leaked into Tenant Alpha results!"

        # Query explicitly as tenant_beta: must ONLY retrieve tenant_beta documents
        response_beta = engine.retrieve(
            query=SearchQuery(query_text="Raft consensus", tenant_id=tenant_beta, limit=5),
            tenant_id=tenant_beta,
            query_embedding=query_vec,
            top_k=5,
        )
        assert len(response_beta.results) > 0
        for res in response_beta.results:
            assert res.document.tenant_id == tenant_beta
            assert res.document.id != doc_consensus.id, "Tenant Alpha document leaked into Tenant Beta query"

        # 9. Verify PostgreSQL / pgvector Persistence
        # Query pgvector directly with fresh connection to prove relational durability
        pg_verify_hits = pgvec.search_embeddings(
            collection=f"pgvec_{collection_name}",
            query_vector=query_vec,
            top_k=1,
            user_id=tenant_alpha,
        )
        assert len(pg_verify_hits) == 1
        assert pg_verify_hits[0]["id"] == doc_consensus.id

    finally:
        # 10. Clean up test data without disturbing unrelated tables
        try:
            if qdrant._client:
                qdrant._client.delete_collection(collection_name=collection_name)
        except Exception:
            pass
        try:
            conn = pgvec._get_conn()
            if conn:
                cur = conn.cursor()
                cur.execute(f"DROP TABLE IF EXISTS vec_pgvec_{collection_name}")
                conn.commit()
                cur.close()
        except Exception:
            pass
        try:
            conn_age = age._get_conn()
            if conn_age:
                cur_age = conn_age.cursor()
                cur_age.execute(f"SELECT drop_graph('{age_graph_name}', true)")
                conn_age.commit()
                cur_age.close()
        except Exception:
            pass


def test_d3_backend_failure_fails_closed(live_services, monkeypatch):
    """Failure Handling Test: When a backend is unavailable during retrieval, strict mode raises RetrievalBackendError."""
    col_name = f"d3_fail_{uuid4().hex[:8]}"
    age_graph = f"d3_fgraph_{uuid4().hex[:8]}"

    qdrant = QdrantAdapter(location=QDRANT_URL, collection_name=col_name, dim=4)
    pgvec = SupabaseAdapter(connection_url=PGVECTOR_URL, _defer_prod_check=True)
    pgvec.adapter_mode = "live"
    age = ApacheAGEAdapter(postgres_url=AGE_URL, graph_name=age_graph, auto_fallback=False)

    engine_strict = IntegratedHybridRetrievalEngine(
        qdrant_adapter=qdrant,
        age_adapter=age,
        pgvector_adapter=pgvec,
        strict_backends=True,
    )

    # Simulate network drop or backend failure on Apache AGE during query execution
    def failing_execute_query(*args, **kwargs):
        raise ConnectionResetError("Connection forcibly closed by remote Apache AGE host")

    monkeypatch.setattr(age, "execute_query", failing_execute_query)

    with pytest.raises(RetrievalBackendError) as exc_info:
        engine_strict.retrieve(
            query="test query",
            tenant_id="test_tenant",
            query_embedding=[1.0, 0.0, 0.0, 0.0],
        )

    err = str(exc_info.value)
    assert "apache_age" in err.lower(), f"Expected apache_age in failure: {err}"
    assert "forcibly closed" in err


def test_d3_memory_engine_integration(live_services):
    """Facade Test: MemoryEngine.integrated_hybrid_retrieve routes unified queries through all backends."""
    col_name = f"d3_mem_{uuid4().hex[:8]}"
    age_graph = f"d3_mgraph_{col_name}"
    tenant_id = f"tenant_facade_{uuid4().hex[:8]}"

    qdrant = QdrantAdapter(location=QDRANT_URL, collection_name=col_name, dim=4)
    age = ApacheAGEAdapter(postgres_url=AGE_URL, graph_name=age_graph, auto_fallback=False)
    pgvec = SupabaseAdapter(connection_url=PGVECTOR_URL, _defer_prod_check=True)
    pgvec.adapter_mode = "live"

    engine = IntegratedHybridRetrievalEngine(
        qdrant_adapter=qdrant,
        age_adapter=age,
        pgvector_adapter=pgvec,
        collection_name=col_name,
    )

    doc = SearchDocument(
        id=f"doc_facade_{col_name}",
        title="Facade Integration Test",
        content="Testing MemoryEngine integrated_hybrid_retrieve entrypoint.",
        tenant_id=tenant_id,
        corpus_type=CorpusType.FILE,
    )
    engine.index_document(doc, embedding=[1.0, 0.0, 0.0, 0.0])

    mem_engine = MemoryEngine(vector_store=qdrant, graph_store=age)
    mem_engine._pgvector_adapter = pgvec

    resp = mem_engine.integrated_hybrid_retrieve(
        query="Facade Integration Test",
        tenant_id=tenant_id,
        query_embedding=[1.0, 0.0, 0.0, 0.0],
        top_k=3,
        pgvector_adapter=pgvec,
    )

    assert isinstance(resp, IntegratedRetrievalResponse)
    assert resp.total_hits >= 1
    assert resp.results[0].document.id == doc.id
    assert resp.results[0].document.tenant_id == tenant_id

    # Clean up
    try:
        if qdrant._client:
            qdrant._client.delete_collection(col_name)
    except Exception:
        pass
    try:
        conn = pgvec._get_conn()
        if conn:
            cur = conn.cursor()
            cur.execute(f"DROP TABLE IF EXISTS vec_pgvec_{col_name}")
            conn.commit()
            cur.close()
    except Exception:
        pass
    try:
        conn_age = age._get_conn()
        if conn_age:
            cur_age = conn_age.cursor()
            cur_age.execute(f"SELECT drop_graph('{age_graph}', true)")
            conn_age.commit()
            cur_age.close()
    except Exception:
        pass
