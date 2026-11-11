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
COMPOSE_SERVICES = ["valkey", "qdrant", "temporal", "keycloak"]


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

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    keycloak_url = os.getenv("KEYCLOAK_URL", "http://localhost:8085")

    _wait_for_http(f"{qdrant_url}/readyz", timeout_s=90.0)
    _wait_for_http(f"{keycloak_url}/realms/master/.well-known/openid-configuration", timeout_s=120.0)

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

