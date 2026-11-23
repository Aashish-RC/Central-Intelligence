"""Legacy End-to-End Tests for Removed Services (Infisical, OpenMeter, SigNoz, Bytebase, LibreChat).

Preserved for historical reference and documentation. These tests are excluded from active
CI and local test runs. To run against the full legacy demo stack:
    COMPOSE_FILE=docker-compose.demo.yml pytest tests/legacy/test_removed_services_e2e.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import pytest

pytestmark = [pytest.mark.live, pytest.mark.requires_provisioned_services, pytest.mark.legacy]


def _required_live_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.fail(f"Required live integration variable {name} is not set", pytrace=False)
    return value


def test_infisical_persists_across_python_restart():
    """Verify Infisical secrets survive Python process restart (F-INT-02)."""
    infisical_url = _required_live_env("INFISICAL_LIVE_URL")

    client_id = _required_live_env("INFISICAL_CLIENT_ID")
    client_secret = _required_live_env("INFISICAL_CLIENT_SECRET")
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


def test_openmeter_persists_across_python_restart():
    """Verify OpenMeter events survive Python process restart (F-INT-04)."""
    openmeter_url = _required_live_env("OPENMETER_LIVE_URL")

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

    # Subprocess 2: query usage from fresh process
    p2 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os, sys
import time
from control.billing.metering.openmeter_adapter import OpenMeterAdapter
adapter = OpenMeterAdapter(endpoint_url='{openmeter_url}', api_token='{api_token}')
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    summary = adapter.query_usage(user_id='{user_id}')
    if summary.total_tokens >= 150:
        sys.exit(0)
    time.sleep(1)
raise AssertionError(f'OpenMeter usage was not persisted; got {{summary.total_tokens}} tokens')
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p2.returncode == 0, f"Process 2 query usage failed: {p2.stderr}"


def test_signoz_persists_across_python_restart():
    """Verify SigNoz traces survive Python process restart (F-INT-05)."""
    signoz_url = _required_live_env("SIGNOZ_LIVE_URL")

    otlp_url = os.getenv("SIGNOZ_OTLP_URL", "http://localhost:4318")
    token = os.getenv("SIGNOZ_API_TOKEN", "")
    op_name = f"e2e_trace_{uuid4().hex[:8]}"

    # Auto-acquire token if not provided in environment
    if not token:
        try:
            admin_email = os.getenv("SIGNOZ_ADMIN_EMAIL", "admin@central-intelligence.local")
            admin_pass = os.getenv("SIGNOZ_ADMIN_PASSWORD", "AdminPassword123!")
            org_id = os.getenv("SIGNOZ_ORG_ID", "")
            if not org_id:
                try:
                    ctx_resp = httpx.get(f"{signoz_url}/api/v2/sessions/context", params={"email": admin_email}, timeout=5.0)
                    if ctx_resp.status_code == 200:
                        orgs = ctx_resp.json().get("data", {}).get("orgs", [])
                        if orgs:
                            org_id = orgs[0].get("id", "")
                except Exception:
                    pass
            if not org_id:
                try:
                    reg_resp = httpx.post(
                        f"{signoz_url}/api/v1/register",
                        json={"email": admin_email, "password": admin_pass, "name": "Admin"},
                        timeout=5.0,
                    )
                    if reg_resp.status_code == 200:
                        org_id = reg_resp.json().get("data", {}).get("orgId", "")
                except Exception:
                    pass
            login_resp = httpx.post(
                f"{signoz_url}/api/v2/sessions/email_password",
                json={"email": admin_email, "password": admin_pass, "orgId": org_id},
                timeout=5.0,
            )
            if login_resp.status_code == 200:
                token = login_resp.json().get("data", {}).get("accessToken", "")
        except Exception:
            pass

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
time.sleep(0.05)
span.end()
from opentelemetry import trace
provider = trace.get_tracer_provider()
if hasattr(provider, 'force_flush'):
    provider.force_flush()
print(span.trace_id)
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p1.returncode == 0, f"Process 1 start trace failed: {p1.stderr}"
    trace_id = p1.stdout.strip().splitlines()[-1]

    # Subprocess 2: query trace from SigNoz
    p2 = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os, sys, time, httpx
deadline = time.monotonic() + 30
headers = {{'Authorization': f'Bearer {token}'}} if '{token}' else {{}}
while time.monotonic() < deadline:
    resp = httpx.get('{signoz_url}/api/v1/traces/{trace_id}', headers=headers, timeout=5.0)
    if resp.status_code != 200:
        resp = httpx.get('{signoz_url}/api/v1/traces', headers=headers, params={{'serviceName': 'central-intelligence'}}, timeout=5.0)
    if resp.status_code == 200 and '{op_name}' in resp.text:
        sys.exit(0)
    time.sleep(1)
raise AssertionError(f'SigNoz did not return trace {trace_id}: HTTP {{resp.status_code}} {{resp.text[:200]}}')
""",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p2.returncode == 0, f"Process 2 query traces failed: {p2.stderr}"


def test_bytebase_migration_executes_real_ddl():
    """Verify Bytebase apply_migration executes real DDL observable in Postgres (F-OPS-02)."""
    bytebase_url = _required_live_env("BYTEBASE_LIVE_URL")

    import pg8000.native
    from platform_infra.release.db.bytebase_adapter import BytebaseAdapter, MigrationStatus

    token = _required_live_env("BYTEBASE_API_TOKEN")
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
    librechat_url = _required_live_env("LIBRECHAT_LIVE_URL")
    response = httpx.get(f"{librechat_url.rstrip('/')}/health", timeout=10.0)
    assert response.status_code == 200

    gateway_url = _required_live_env("REASONING_GATEWAY_URL")

    from surface.interaction.web.librechat_adapter import LibreChatAdapter

    adapter = LibreChatAdapter(
        gateway_url=gateway_url,
        api_key=_required_live_env("REASONING_GATEWAY_API_KEY"),
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
