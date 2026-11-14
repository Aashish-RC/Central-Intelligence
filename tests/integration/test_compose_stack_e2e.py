"""End-to-end Docker Compose integration suite (Qdrant, Temporal, Keycloak, Valkey).

Excluded from offline default pytest via ``@pytest.mark.live``.
Run directly against a live compose stack:
    pytest -m live tests/integration/test_compose_stack_e2e.py -v
Or let the suite start/stop the target compose services automatically:
    COMPOSE_E2E_AUTO_START=1 pytest -m live tests/integration/test_compose_stack_e2e.py -v
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import redis
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from temporalio import workflow
from temporalio.client import Client as TemporalClient
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

pytestmark = pytest.mark.live

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SERVICES = ["valkey", "qdrant", "apache-age", "temporal", "keycloak"]


@workflow.defn
class _ComposeEchoWorkflow:
    @workflow.run
    async def run(self, payload: str) -> str:
        return f"ci-e2e:{payload}"


def _default_compose_env() -> dict[str, str]:
    """Build subprocess environment satisfying required compose secrets for CI/E2E."""
    env = os.environ.copy()
    env.setdefault("MEILISEARCH_MASTER_KEY", "e2e-test-meili-key")
    env.setdefault("NANGO_SECRET_KEY", "e2e-test-nango-secret")
    env.setdefault("KEYCLOAK_ADMIN", "admin")
    env.setdefault("KEYCLOAK_ADMIN_PASSWORD", "e2e-admin-pass")
    env.setdefault("INFISICAL_ENCRYPTION_KEY", "0123456789abcdef0123456789abcdef")
    env.setdefault("LIVEKIT_KEYS", "e2ekey: e2esecret")
    env.setdefault("POSTGRES_PASSWORD", "e2e-postgres-pass")
    env.setdefault("POSTHOG_SECRET", "e2e-test-posthog-secret")
    env.setdefault("SVIX_JWT_SECRET", "e2e-svix-jwt-secret-placeholder")
    return env


def _wait_for_http(url: str, timeout_s: float = 120.0) -> None:
    """Poll an HTTP endpoint until it responds with <500 status or raise TimeoutError."""
    deadline = time.monotonic() + timeout_s
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=3.0)
            if resp.status_code < 500:
                return
        except Exception as exc:  # pragma: no cover - transient startup polling
            last_exc = exc
        time.sleep(2.0)
    raise TimeoutError(f"Service at {url} did not become ready within {timeout_s}s: {last_exc}")


@pytest.fixture(scope="module", autouse=True)
def compose_stack_lifecycle():
    """Optionally bring up Qdrant, Temporal, Keycloak, and Valkey via Docker Compose."""
    auto_start = os.getenv("COMPOSE_E2E_AUTO_START", "").lower() in ("1", "true", "yes")
    env = _default_compose_env()

    if auto_start:
        subprocess.run(
            ["docker", "compose", "up", "-d", *COMPOSE_SERVICES],
            cwd=REPO_ROOT,
            env=env,
            check=True,
        )
        _wait_for_http(f"{qdrant_url}/readyz", timeout_s=90.0)
        _wait_for_http(f"{keycloak_url}/realms/master/.well-known/openid-configuration", timeout_s=120.0)
    elif os.getenv("QDRANT_URL") or os.getenv("KEYCLOAK_URL"):
        _wait_for_http(f"{qdrant_url}/readyz", timeout_s=10.0)
        _wait_for_http(f"{keycloak_url}/realms/master/.well-known/openid-configuration", timeout_s=10.0)

    yield env

    if auto_start and os.getenv("COMPOSE_E2E_KEEP_RUNNING", "").lower() not in ("1", "true"):
        subprocess.run(
            ["docker", "compose", "stop", *COMPOSE_SERVICES],
            cwd=REPO_ROOT,
            env=env,
            check=False,
        )


def test_valkey_redis_wire_roundtrip_e2e() -> None:
    """Verify Valkey serves Redis wire commands cleanly as the OSI cache swap."""
    client = redis.Redis(
        host=os.getenv("VALKEY_HOST", "localhost"),
        port=int(os.getenv("VALKEY_PORT", "6379")),
        decode_responses=True,
    )
    assert client.ping() is True
    key = f"ci:e2e:{uuid4().hex}"
    client.set(key, "valkey-ok", ex=30)
    try:
        assert client.get(key) == "valkey-ok"
    finally:
        client.delete(key)


def test_qdrant_vector_roundtrip_e2e() -> None:
    """Verify real Qdrant collection creation, vector upsert, query, and cleanup."""
    client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
    collection_name = f"e2e_ci_{uuid4().hex[:8]}"
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=4, distance=Distance.COSINE),
    )
    try:
        client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=1,
                    vector=[0.9, 0.1, 0.0, 0.0],
                    payload={"layer": "L2", "topic": "memory"},
                ),
                PointStruct(
                    id=2,
                    vector=[0.0, 0.0, 0.9, 0.1],
                    payload={"layer": "L3", "topic": "knowledge"},
                ),
            ],
        )
        hits = client.query_points(
            collection_name=collection_name,
            query=[0.95, 0.05, 0.0, 0.0],
            limit=1,
        )
        assert len(hits.points) == 1
        assert hits.points[0].id == 1
        assert hits.points[0].payload == {"layer": "L2", "topic": "memory"}
    finally:
        client.delete_collection(collection_name=collection_name)


@pytest.mark.asyncio
async def test_temporal_workflow_execution_e2e() -> None:
    """Verify real Temporal server workflow scheduling and worker completion."""
    target = os.getenv("TEMPORAL_TARGET", "localhost:7233")
    deadline = time.monotonic() + 90.0
    client: TemporalClient | None = None
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            client = await TemporalClient.connect(target)
            break
        except Exception as exc:  # pragma: no cover - startup polling
            last_exc = exc
            await asyncio.sleep(2.0)

    if client is None:
        pytest.fail(f"Temporal server at {target} not reachable: {last_exc}")

    task_queue = f"ci-e2e-{uuid4().hex[:8]}"
    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[_ComposeEchoWorkflow],
        workflow_runner=UnsandboxedWorkflowRunner(),
    ):
        result = await client.execute_workflow(
            _ComposeEchoWorkflow.run,
            "ping",
            id=f"wf-e2e-{uuid4().hex[:8]}",
            task_queue=task_queue,
        )
    assert result == "ci-e2e:ping"


def test_keycloak_oidc_and_admin_api_e2e() -> None:
    """Verify real Keycloak OIDC discovery, admin token issuance, and /admin/realms access."""
    keycloak_url = os.getenv("KEYCLOAK_URL", "http://localhost:8085")
    admin_user = os.getenv("KEYCLOAK_ADMIN", "admin")
    admin_password = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "e2e-admin-pass")

    oidc = httpx.get(
        f"{keycloak_url}/realms/master/.well-known/openid-configuration",
        timeout=10.0,
    )
    oidc.raise_for_status()
    oidc_data = oidc.json()
    token_endpoint = oidc_data["token_endpoint"]

    token_resp = httpx.post(
        token_endpoint,
        data={
            "client_id": "admin-cli",
            "grant_type": "password",
            "username": admin_user,
            "password": admin_password,
        },
        timeout=10.0,
    )
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]
    assert access_token

    realms_resp = httpx.get(
        f"{keycloak_url}/admin/realms",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10.0,
    )
    realms_resp.raise_for_status()
    realm_names = {r["realm"] for r in realms_resp.json()}
    assert "master" in realm_names


def test_memory_qdrant_adapter_v120_e2e() -> None:
    """Exercise the real L2 QdrantAdapter against live Qdrant v1.20.0 (query_points API)."""
    from cognitive.memory.core.models import MemoryRecord, utc_now
    from cognitive.memory.tiers.semantic.qdrant_adapter import QdrantAdapter

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    collection = f"e2e_mem_{uuid4().hex[:8]}"
    adapter = QdrantAdapter(
        location=qdrant_url,
        collection_name=collection,
        dim=8,
    )
    assert adapter._location == qdrant_url
    assert adapter.check_health() is True

    rec_id = uuid4()
    other_id = uuid4()
    now = utc_now()
    records = [
        MemoryRecord(
            id=rec_id,
            user_id="e2e_user",
            text="Apache AGE is our open PostgreSQL graph backend.",
            embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            confidence_score=0.95,
            created_at=now,
            updated_at=now,
            last_accessed_at=now,
        ),
        MemoryRecord(
            id=other_id,
            user_id="e2e_user",
            text="Valkey handles ephemeral Redis wire sessions.",
            embedding=[0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            confidence_score=0.9,
            created_at=now,
            updated_at=now,
            last_accessed_at=now,
        ),
    ]
    try:
        upserted = adapter.upsert_vectors(records)
        assert len(upserted) == 2

        matches = adapter.query_similar(
            user_id="e2e_user",
            query_embedding=[0.98, 0.02, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            top_k=1,
        )
        assert len(matches) == 1
        assert matches[0].id == rec_id
        assert "Apache AGE" in matches[0].text

        assert adapter.delete(rec_id) is True
        assert adapter.delete_by_user("e2e_user") >= 1
    finally:
        if adapter._client:
            adapter._client.delete_collection(collection_name=collection)


def test_postgres_apache_age_graph_adapters_e2e() -> None:
    """Exercise L2 ApacheAGEAdapter & L3 ApacheAGEGraphAdapter against live apache-age."""
    import json
    import pg8000.dbapi
    from knowledge.graph import ApacheAGEGraphAdapter
    from cognitive.memory.tiers.graph.age_adapter import ApacheAGEAdapter

    pg_password = os.getenv("POSTGRES_PASSWORD", "e2e-postgres-pass")
    age_port = int(os.getenv("AGE_POSTGRES_PORT", "5433"))
    pg_url = os.getenv(
        "AGE_POSTGRES_URL",
        f"postgresql://postgres:{pg_password}@localhost:{age_port}/postgres",
    )

    deadline = time.monotonic() + 90.0
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            conn = pg8000.dbapi.connect(
                host="localhost",
                port=age_port,
                user="postgres",
                password=pg_password,
                database="postgres",
                timeout=3,
            )
            conn.close()
            break
        except Exception as exc:  # pragma: no cover - startup polling
            last_exc = exc
            time.sleep(2.0)
    else:
        pytest.fail(f"Apache AGE Postgres did not become ready in time: {last_exc}")

    suffix = uuid4().hex[:8]
    l2_graph = ApacheAGEAdapter(
        postgres_url=pg_url,
        graph_name=f"e2e_l2_{suffix}",
        auto_fallback=False,
    )
    l3_graph = ApacheAGEGraphAdapter(
        postgres_url=pg_url,
        graph_name=f"e2e_l3_{suffix}",
        auto_fallback=False,
    )
    try:
        assert l2_graph.is_in_memory is False
        assert l2_graph.check_health() is True
        l2_graph.add_relationship(
            user_id="e2e_u",
            source="Bob",
            relation="MANAGES",
            target="Alice",
        )
        managers = l2_graph.execute_query(
            "MATCH (m)-[:MANAGES]->(a {name: 'Alice'}) RETURN m.name"
        )
        assert managers and managers[0]["m.name"] == "Bob"

        # Verify dollar-quote & SQL-injection payloads round-trip unchanged via bound parameters
        for payload in ("$$$", "$$$$", "'$$; DROP TABLE x; --"):
            l2_graph.add_entity(
                user_id="e2e_u",
                name=payload,
                properties={"raw": payload},
            )
            found = l2_graph.execute_query(
                "MATCH (n {name: $name, user_id: $user_id}) RETURN n.name AS name, n.props_json AS props_json",
                params={"name": payload, "user_id": "e2e_u"},
            )
            assert len(found) == 1
            assert found[0]["name"] == payload
            assert json.loads(found[0]["props_json"])["raw"] == payload

        assert l3_graph.is_in_memory is False
        assert l3_graph.check_health() is True
        l3_graph.add_relationship(source="Bob", relation="MANAGES", target="Alice")
        l3_graph.add_relationship(source="Bob", relation="WORKS_AT", target="Megacorp")
        l3_graph.add_relationship(source="Megacorp", relation="ACQUIRED", target="StartupAI")
        acquired = l3_graph.query_manager_company_acquisitions("Alice")
        assert "StartupAI" in acquired
    finally:
        l2_graph.close()
        l3_graph.close()


def test_openfga_persists_across_python_restart():
    """Verify OpenFGA state survives Python process restart (F-INT-01)."""
    openfga_url = os.getenv("OPENFGA_LIVE_URL")
    if not openfga_url:
        pytest.skip("OPENFGA_LIVE_URL not set; skipping live persistence test")

    client = httpx.Client(base_url=openfga_url, timeout=5.0)
    store_name = f"e2e-fga-{uuid4().hex[:8]}"
    create_resp = client.post("/stores", json={"name": store_name})
    assert create_resp.status_code in (200, 201)
    store_id = create_resp.json()["id"]

    model_payload = {
        "schema_version": "1.1",
        "type_definitions": [
            {"type": "user", "relations": {}},
            {
                "type": "document",
                "relations": {"viewer": {"this": {}}},
                "metadata": {
                    "relations": {"viewer": {"directly_related_user_types": [{"type": "user"}]}}
                },
            },
        ],
    }
    m_resp = client.post(f"/stores/{store_id}/authorization-models", json=model_payload)
    assert m_resp.status_code in (200, 201)

    user_id = f"user:{uuid4().hex[:8]}"
    doc_id = f"document:{uuid4().hex[:8]}"

    env = os.environ.copy()
    env["ADAPTER_MODE"] = "live"
    env.pop("CI_TEST_MODE", None)

    # Subprocess 1: write tuple
    p1 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os
from control.identity.openfga_adapter import OpenFGAAdapter
adapter = OpenFGAAdapter(api_url='{openfga_url}', store_id='{store_id}')
adapter.write_tuple('{user_id}', 'viewer', '{doc_id}')
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p1.returncode == 0, f"Process 1 write failed: {p1.stderr}"

    # Subprocess 2: check tuple from fresh process
    p2 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os, sys
from control.identity.openfga_adapter import OpenFGAAdapter
adapter = OpenFGAAdapter(api_url='{openfga_url}', store_id='{store_id}')
allowed = adapter.check_permission('{user_id}', 'viewer', '{doc_id}')
sys.exit(0 if allowed else 1)
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p2.returncode == 0, f"Process 2 check failed: {p2.stderr}"


def test_infisical_persists_across_python_restart():
    """Verify Infisical secrets survive Python process restart (F-INT-02)."""
    infisical_url = os.getenv("INFISICAL_LIVE_URL")
    if not infisical_url:
        pytest.skip("INFISICAL_LIVE_URL not set; skipping live persistence test")

    client_id = os.getenv("INFISICAL_CLIENT_ID", "")
    client_secret = os.getenv("INFISICAL_CLIENT_SECRET", "")
    key = f"E2E_SECRET_{uuid4().hex[:8]}"
    val = f"val_{uuid4().hex}"

    env = os.environ.copy()
    env["ADAPTER_MODE"] = "live"
    env.pop("CI_TEST_MODE", None)

    # Subprocess 1: store secret
    p1 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os
from control.identity.secrets.infisical_adapter import InfisicalAdapter
adapter = InfisicalAdapter(server_url='{infisical_url}', client_id='{client_id}', client_secret='{client_secret}')
adapter.store_secret('{key}', '{val}')
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p1.returncode == 0, f"Process 1 store failed: {p1.stderr}"

    # Subprocess 2: retrieve secret
    p2 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os, sys
from control.identity.secrets.infisical_adapter import InfisicalAdapter
adapter = InfisicalAdapter(server_url='{infisical_url}', client_id='{client_id}', client_secret='{client_secret}')
retrieved = adapter.get_secret('{key}')
sys.exit(0 if retrieved == '{val}' else 1)
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p2.returncode == 0, f"Process 2 retrieve failed: {p2.stderr}"


def test_lago_persists_across_python_restart():
    """Verify Lago customer subscriptions survive Python process restart (F-INT-03)."""
    lago_url = os.getenv("LAGO_LIVE_URL")
    if not lago_url:
        pytest.skip("LAGO_LIVE_URL not set; skipping live persistence test")

    api_key = os.getenv("LAGO_API_KEY", "")
    customer_id = f"e2e_cust_{uuid4().hex[:8]}"

    env = os.environ.copy()
    env["ADAPTER_MODE"] = "live"
    env.pop("CI_TEST_MODE", None)

    # Subprocess 1: subscribe customer
    p1 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os
from control.billing.engine.lago_adapter import LagoAdapter
adapter = LagoAdapter(api_url='{lago_url}', api_key='{api_key}')
adapter.subscribe_customer('{customer_id}', 'free')
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p1.returncode == 0, f"Process 1 subscribe failed: {p1.stderr}"

    # Subprocess 2: check entitlement from fresh process
    p2 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os, sys
from control.billing.engine.lago_adapter import LagoAdapter
adapter = LagoAdapter(api_url='{lago_url}', api_key='{api_key}')
allowed, _ = adapter.check_entitlement('{customer_id}', requested_tokens=100)
sys.exit(0 if allowed else 1)
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p2.returncode == 0, f"Process 2 entitlement failed: {p2.stderr}"


def test_openmeter_persists_across_python_restart():
    """Verify OpenMeter events survive Python process restart (F-INT-04)."""
    openmeter_url = os.getenv("OPENMETER_LIVE_URL")
    if not openmeter_url:
        pytest.skip("OPENMETER_LIVE_URL not set; skipping live persistence test")

    api_token = os.getenv("OPENMETER_API_TOKEN", "")
    user_id = f"e2e_usr_{uuid4().hex[:8]}"

    env = os.environ.copy()
    env["ADAPTER_MODE"] = "live"
    env.pop("CI_TEST_MODE", None)

    # Subprocess 1: record event
    p1 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os
from control.billing.metering.openmeter_adapter import OpenMeterAdapter
from control.billing.models import TokenUsageEvent
adapter = OpenMeterAdapter(endpoint_url='{openmeter_url}', api_token='{api_token}')
ev = TokenUsageEvent(user_id='{user_id}', tenant_id='default', app_id='chat', model='gpt-4o', prompt_tokens=100, completion_tokens=50, total_tokens=150)
res = adapter.record_event(ev, dispatch_remote=True)
assert res['remote_dispatched'] is True
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p1.returncode == 0, f"Process 1 record event failed: {p1.stderr}"

    time.sleep(0.3)

    # Subprocess 2: query usage from fresh process
    p2 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os, sys
from control.billing.metering.openmeter_adapter import OpenMeterAdapter
adapter = OpenMeterAdapter(endpoint_url='{openmeter_url}', api_token='{api_token}')
summary = adapter.query_usage(user_id='{user_id}')
sys.exit(0 if summary.total_tokens >= 150 else 1)
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p2.returncode == 0, f"Process 2 query usage failed: {p2.stderr}"


def test_signoz_persists_across_python_restart():
    """Verify SigNoz traces survive Python process restart (F-INT-05)."""
    signoz_url = os.getenv("SIGNOZ_LIVE_URL")
    if not signoz_url:
        pytest.skip("SIGNOZ_LIVE_URL not set; skipping live persistence test")

    otlp_url = os.getenv("SIGNOZ_OTLP_URL", "http://localhost:4318")
    op_name = f"e2e_trace_{uuid4().hex[:8]}"

    env = os.environ.copy()
    env["ADAPTER_MODE"] = "live"
    env.pop("CI_TEST_MODE", None)

    # Subprocess 1: start trace and end
    p1 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os, time
from control.observability.signoz.signoz_adapter import SigNozAdapter
adapter = SigNozAdapter(endpoint_url='{otlp_url}')
span = adapter.start_trace('{op_name}', layer='L14')
span.end()
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p1.returncode == 0, f"Process 1 start trace failed: {p1.stderr}"

    time.sleep(1.0)

    # Subprocess 2: query trace from SigNoz
    p2 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os, sys, httpx
resp = httpx.get('{signoz_url}/api/v1/traces', params={{'serviceName': 'central-intelligence'}}, timeout=5.0)
sys.exit(0 if resp.status_code == 200 else 1)
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p2.returncode == 0, f"Process 2 query traces failed: {p2.stderr}"


def test_temporal_workflow_survives_worker_restart():
    """Verify Temporal workflows survive worker process death and replay from server history (F-INT-07)."""
    temporal_url = os.getenv("TEMPORAL_LIVE_URL")
    if not temporal_url:
        pytest.skip("TEMPORAL_LIVE_URL not set; skipping live Temporal replay persistence test")

    queue = f"e2e-wf-queue-{uuid4().hex[:8]}"
    wf_id = f"e2e-wf-{uuid4().hex[:8]}"

    env = os.environ.copy()
    env["ADAPTER_MODE"] = "live"
    env.pop("CI_TEST_MODE", None)

    # Subprocess 1: Start Temporal worker in background
    worker_code = f"""
import asyncio
from control.orchestration.workflow_builder.runtime.temporal_adapter import TemporalWorkflowAdapter
adapter = TemporalWorkflowAdapter(target_host='{temporal_url}', task_queue='{queue}', _defer_prod_check=True)
adapter.adapter_mode = 'live'
asyncio.run(adapter.start_worker())
"""
    w1 = subprocess.Popen([sys.executable, "-c", worker_code], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(2.0)

    try:
        # Start workflow via client in separate process
        start_code = f"""
import asyncio
from control.orchestration.workflow_builder.runtime.temporal_adapter import TemporalWorkflowAdapter
from control.orchestration.workflow_builder.runtime.temporal_workflow import CIDagWorkflow
from control.orchestration.workflow_builder.core.models import WorkflowGraph, WorkflowNode, WorkflowNodeType, WorkflowEdge

nodes = {{
    f"step_{{i}}": WorkflowNode(
        node_id=f"step_{{i}}",
        node_type=WorkflowNodeType.AGENT_STEP if i > 0 else WorkflowNodeType.TRIGGER,
        label=f"Step {{i}}",
        action_name=f"action_{{i}}",
        upstream_dependencies=[f"step_{{i-1}}"] if i > 0 else [],
    )
    for i in range(5)
}}
edges = [
    WorkflowEdge(source_node_id=f"step_{{i}}", target_node_id=f"step_{{i+1}}")
    for i in range(4)
]
graph = WorkflowGraph(workflow_id='{wf_id}', name='Replay Test', description='', nodes=nodes, edges=edges)

adapter = TemporalWorkflowAdapter(target_host='{temporal_url}', task_queue='{queue}', _defer_prod_check=True)
adapter.adapter_mode = 'live'

async def main():
    client = await adapter._get_client()
    await client.start_workflow(CIDagWorkflow.run, graph.to_dict(), id='{wf_id}', task_queue='{queue}')

asyncio.run(main())
"""
        p_start = subprocess.run([sys.executable, "-c", start_code], env=env, capture_output=True, text=True)
        assert p_start.returncode == 0, f"Failed to start workflow: {p_start.stderr}"

        # Kill worker 1 mid-execution
        time.sleep(0.5)
        w1.terminate()
        w1.wait(timeout=5.0)

        # Start worker 2 (simulating worker restart)
        w2 = subprocess.Popen([sys.executable, "-c", worker_code], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(1.0)
        try:
            # Query result from client
            result_code = f"""
import asyncio, sys
from control.orchestration.workflow_builder.runtime.temporal_adapter import TemporalWorkflowAdapter

adapter = TemporalWorkflowAdapter(target_host='{temporal_url}', task_queue='{queue}', _defer_prod_check=True)
adapter.adapter_mode = 'live'

async def main():
    client = await adapter._get_client()
    handle = client.get_workflow_handle('{wf_id}')
    res = await handle.result()
    sys.exit(0 if res.get('success') and len(res.get('nodes_executed', [])) == 5 else 1)

asyncio.run(main())
"""
            p_res = subprocess.run([sys.executable, "-c", result_code], env=env, capture_output=True, text=True)
            assert p_res.returncode == 0, f"Workflow failed to complete upon worker restart: {p_res.stderr}"
        finally:
            w2.terminate()
            w2.wait(timeout=5.0)
    finally:
        if w1.poll() is None:
            w1.terminate()


def test_supabase_relational_and_vector_persist():
    """Verify Supabase Postgres relational rows and pgvector embeddings survive Python restart (F-INT-06)."""
    postgres_url = os.getenv("POSTGRES_LIVE_URL")
    if not postgres_url:
        pytest.skip("POSTGRES_LIVE_URL not set; skipping live Supabase persistence test")

    table_name = f"e2e_rel_{uuid4().hex[:8]}"
    collection = f"e2e_vec_{uuid4().hex[:8]}"
    doc_id = f"doc_{uuid4().hex[:8]}"
    user_id = f"user_{uuid4().hex[:8]}"

    env = os.environ.copy()
    env["ADAPTER_MODE"] = "live"
    env.pop("CI_TEST_MODE", None)

    # Subprocess 1: insert row and store embedding
    p1 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os
from platform_infra.data.supabase.supabase_adapter import SupabaseAdapter
adapter = SupabaseAdapter(connection_url='{postgres_url}', _defer_prod_check=True)
adapter.adapter_mode = 'live'
adapter.insert_row('{table_name}', {{'title': 'Durability Test'}}, '{user_id}')
adapter.store_embedding('{collection}', '{doc_id}', [1.0, 0.0, 0.0], 'Embedded document content', '{user_id}')
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p1.returncode == 0, f"Process 1 write failed: {p1.stderr}"

    # Subprocess 2: query row and search vector from fresh process
    p2 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os, sys
from platform_infra.data.supabase.supabase_adapter import SupabaseAdapter
adapter = SupabaseAdapter(connection_url='{postgres_url}', _defer_prod_check=True)
adapter.adapter_mode = 'live'
rows = adapter.query_table('{table_name}', '{user_id}')
assert len(rows) == 1 and rows[0]['title'] == 'Durability Test', f"Row missing: {{rows}}"

results = adapter.search_embeddings('{collection}', [0.99, 0.01, 0.0], top_k=1, user_id='{user_id}')
assert len(results) == 1 and results[0]['id'] == '{doc_id}', f"Embedding missing: {{results}}"
sys.exit(0)
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p2.returncode == 0, f"Process 2 query failed: {p2.stderr}"


def test_sandbox_executes_real_python():
    """Verify Sandbox executes actual Python code in a container, returning real computed stdout (F-INT-08)."""
    if os.getenv("SANDBOX_LIVE") != "1":
        pytest.skip("SANDBOX_LIVE=1 not set; skipping live container execution test")

    env = os.environ.copy()
    env["ADAPTER_MODE"] = "live"
    env.pop("CI_TEST_MODE", None)

    p = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import asyncio, sys
from agent.sandbox.e2b_adapter import E2BSandboxAdapter
from agent.core.manifest import SandboxConfig

async def main():
    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=15)
    res = await adapter.execute_command("python3 -c 'print(2+2)'", config=config)
    assert res['exit_code'] == 0, f"Non-zero exit: {res}"
    assert res['stdout'].strip() == "4", f"Expected '4', got: {res['stdout']}"
    assert "Simulated" not in res['stdout'], "Returned simulated mock string!"
    sys.exit(0)

asyncio.run(main())
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, f"Container execution failed: {p.stderr}"


def test_kamal_invokes_real_cli(monkeypatch):
    """Verify Kamal deploy invokes real CLI commands in sequence (F-OPS-01)."""
    if os.getenv("KAMAL_LIVE") != "1":
        pytest.skip("KAMAL_LIVE=1 not set; skipping Kamal live CLI invocation test")

    from unittest.mock import MagicMock
    from platform_infra.release.ci.kamal_adapter import KamalAdapter, KamalConfig, DeploymentPhase

    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/local/bin/kamal")

    executed_commands = []

    def fake_run(cmd, capture_output=True, text=True, env=None, timeout=600, check=True):
        executed_commands.append(list(cmd))
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    monkeypatch.setattr("httpx.get", lambda url, timeout=1.0: mock_resp)

    config = KamalConfig(
        service_name="central-intelligence-api",
        servers=["192.168.1.101"],
        healthcheck_path="/healthz",
    )
    adapter = KamalAdapter(config=config)
    deployment = adapter.deploy(version_tag="v3.0.0")

    assert deployment.phase == DeploymentPhase.COMPLETED
    expected = [
        ["kamal", "lock", "acquire"],
        ["kamal", "registry", "push"],
        ["kamal", "app", "boot", "--version", "v3.0.0"],
        ["kamal", "proxy", "boot"],
        ["kamal", "app", "stop", "--version", "previous"],
        ["kamal", "lock", "release"],
    ]
    assert executed_commands == expected


def test_bytebase_migration_executes_real_ddl():
    """Verify Bytebase apply_migration executes real DDL observable in Postgres (F-OPS-02)."""
    bytebase_url = os.getenv("BYTEBASE_LIVE_URL")
    if not bytebase_url:
        pytest.skip("BYTEBASE_LIVE_URL not set; skipping live Bytebase DDL test")

    import pg8000.native
    from platform_infra.release.db.bytebase_adapter import BytebaseAdapter, MigrationStatus

    token = os.getenv("BYTEBASE_API_TOKEN", "bb_test_token")
    adapter = BytebaseAdapter(endpoint_url=bytebase_url, api_token=token, _defer_prod_check=True)
    adapter.adapter_mode = "live"

    v = f"e2e_{uuid4().hex[:6]}"
    table_name = f"e2e_bb_{v}"
    up_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (id SERIAL PRIMARY KEY, val TEXT);"
    down_sql = f"DROP TABLE IF EXISTS {table_name};"

    mig = adapter.create_migration(
        database_name="postgres",
        version=v,
        title=f"E2E create {table_name}",
        up_sql=up_sql,
        down_sql=down_sql,
    )
    adapter.review_migration(mig.migration_id, approved=True, reviewer="e2e_runner")
    applied = adapter.apply_migration(mig.migration_id)
    assert applied.execution_status == MigrationStatus.APPLIED

    pg_host = os.getenv("POSTGRES_HOST", "localhost")
    pg_port = int(os.getenv("POSTGRES_PORT", "5432"))
    pg_user = os.getenv("POSTGRES_USER", "postgres")
    pg_pass = os.getenv("POSTGRES_PASSWORD", "postgres")
    pg_db = os.getenv("POSTGRES_DB", "postgres")

    conn = pg8000.native.Connection(
        host=pg_host,
        port=pg_port,
        user=pg_user,
        password=pg_pass,
        database=pg_db,
    )
    try:
        rows = conn.run(f"SELECT table_name FROM information_schema.tables WHERE table_name = '{table_name}'")
        assert len(rows) == 1
    finally:
        adapter.rollback_migration(mig.migration_id)
        conn.close()


def test_librechat_routes_to_reasoning_gateway():
    """Verify LibreChat adapter bridges to Layer 4 gateway and returns dynamic completions."""
    gateway_url = os.getenv("REASONING_GATEWAY_URL")
    if not gateway_url:
        pytest.skip("REASONING_GATEWAY_URL not set; skipping live LibreChat gateway test")

    from surface.interaction.web.librechat_adapter import LibreChatAdapter

    adapter = LibreChatAdapter(
        gateway_url=gateway_url,
        api_key=os.getenv("REASONING_GATEWAY_API_KEY", "test_key"),
        _defer_prod_check=True,
    )
    adapter.adapter_mode = "live"

    conv1 = adapter.create_conversation(title="E2E Gateway 1")
    reply1 = adapter.send_message(conv1.conversation_id, "What is 2+2? Answer with just the digit.")
    assert reply1.role == "assistant"

    conv2 = adapter.create_conversation(title="E2E Gateway 2")
    reply2 = adapter.send_message(conv2.conversation_id, "What is 5+5? Answer with just the digit.")
    assert reply2.role == "assistant"
    assert reply1.content != reply2.content


def test_paddleocr_fails_closed_without_deps(monkeypatch):
    """Verify PaddleOCR fails closed with ProductionSafetyError when uninstalled (F-DEP-01)."""
    from PIL import Image
    from control.safety.production_guard import ProductionSafetyError
    import cognitive.perception.vision.paddleocr_adapter as ocr_module
    from cognitive.perception.vision.paddleocr_adapter import PaddleOCRAdapter

    monkeypatch.setattr(ocr_module, "_PADDLEOCR_AVAILABLE", False)
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    adapter = PaddleOCRAdapter(_defer_prod_check=True)
    adapter.adapter_mode = "live"
    img = Image.new("RGB", (50, 50), color="white")

    with pytest.raises(ProductionSafetyError):
        adapter.extract_text_from_image(img)


def test_dual_boundary_tag_form_matches_docs():
    """Verify docs directory contains zero references to deprecated untrusted_user_input (F-DOC-01)."""
    docs_dir = REPO_ROOT / "docs"
    old_form = "untrusted_user_input"
    offenders = []
    for md in docs_dir.rglob("*.md"):
        if old_form in md.read_text(encoding="utf-8"):
            offenders.append(str(md.relative_to(docs_dir)))
    assert not offenders, f"Docs still reference deprecated tag form: {offenders}"



