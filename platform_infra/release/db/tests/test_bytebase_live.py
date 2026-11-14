"""Live integration tests for BytebaseAdapter REST API (Milestone 4 - Task 4.2)."""

import os
from unittest.mock import MagicMock

import httpx
import pytest
from control.safety.production_guard import ProductionSafetyError
from platform_infra.release.db.bytebase_adapter import (
    BytebaseAdapter,
    MigrationStatus,
    ReviewStatus,
)


@pytest.fixture
def live_bytebase_url():
    url = os.getenv("BYTEBASE_LIVE_URL")
    if not url:
        pytest.skip("Requires BYTEBASE_LIVE_URL env var")
    return url.rstrip("/")


@pytest.fixture
def live_adapter(live_bytebase_url, monkeypatch):
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    token = os.getenv("BYTEBASE_API_TOKEN", "bb_test_token")
    return BytebaseAdapter(endpoint_url=live_bytebase_url, api_token=token)


@pytest.mark.live
def test_migration_persists_in_bytebase(live_adapter, live_bytebase_url):
    """create_migration() POSTs to Bytebase and persists an issue."""
    v = "20261114_001"
    title = f"Test Migration {v}"
    up_sql = "CREATE TABLE test_items (id SERIAL PRIMARY KEY, label TEXT);"
    down_sql = "DROP TABLE test_items;"

    mig = live_adapter.create_migration(
        database_name="central_postgres",
        version=v,
        title=title,
        up_sql=up_sql,
        down_sql=down_sql,
    )
    assert mig.review_status == ReviewStatus.PENDING_REVIEW

    # Verify issue in Bytebase
    resp = httpx.get(
        f"{live_bytebase_url}/v1/projects/{live_adapter.project_id}/issues",
        headers=live_adapter._auth_headers(),
        timeout=10.0,
    )
    assert resp.status_code == 200
    issues = resp.json()
    issues_list = issues if isinstance(issues, list) else issues.get("issues", [])
    found = any(title in str(item) or up_sql in str(item) for item in issues_list)
    assert found or mig.metadata.get("bytebase_issue_id")


@pytest.mark.live
def test_apply_migration_executes_real_ddl(live_adapter):
    """apply_migration() executes DDL in target Postgres observable via pg8000."""
    import pg8000.native

    v = "20261114_002"
    table_name = f"users_m4_{v}"
    up_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (id SERIAL PRIMARY KEY, name TEXT);"
    down_sql = f"DROP TABLE IF EXISTS {table_name};"

    mig = live_adapter.create_migration(
        database_name="postgres",
        version=v,
        title=f"Add {table_name} table",
        up_sql=up_sql,
        down_sql=down_sql,
    )
    live_adapter.review_migration(mig.migration_id, approved=True, reviewer="lead_dba")
    applied = live_adapter.apply_migration(mig.migration_id)

    assert applied.execution_status == MigrationStatus.APPLIED

    # Verify in target Postgres
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
        rows = conn.run(
            f"SELECT table_name FROM information_schema.tables WHERE table_name = '{table_name}'"
        )
        assert len(rows) == 1
    finally:
        conn.close()


@pytest.mark.live
def test_rollback_executes_down_sql(live_adapter):
    """rollback_migration() executes down_sql dropping the table in Postgres."""
    import pg8000.native

    v = "20261114_003"
    table_name = f"users_m4_{v}"
    up_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (id SERIAL PRIMARY KEY, name TEXT);"
    down_sql = f"DROP TABLE IF EXISTS {table_name};"

    mig = live_adapter.create_migration(
        database_name="postgres",
        version=v,
        title=f"Add {table_name} table",
        up_sql=up_sql,
        down_sql=down_sql,
    )
    live_adapter.review_migration(mig.migration_id, approved=True, reviewer="lead_dba")
    live_adapter.apply_migration(mig.migration_id)

    rolled_back = live_adapter.rollback_migration(mig.migration_id)
    assert rolled_back.execution_status == MigrationStatus.ROLLED_BACK

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
        rows = conn.run(
            f"SELECT table_name FROM information_schema.tables WHERE table_name = '{table_name}'"
        )
        assert len(rows) == 0
    finally:
        conn.close()


@pytest.mark.live
def test_bytebase_down_fails_closed(monkeypatch):
    """When Bytebase is unreachable and ADAPTER_MODE=live, operations raise ProductionSafetyError."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    adapter = BytebaseAdapter(
        endpoint_url="http://127.0.0.1:59999",
        api_token="dummy_token",
        _defer_prod_check=True,
    )
    adapter.adapter_mode = "live"

    with pytest.raises(ProductionSafetyError):
        adapter.create_migration(
            database_name="postgres",
            version="001",
            title="Fail closed test",
            up_sql="CREATE TABLE test_fail (id INT);",
            down_sql="DROP TABLE test_fail;",
        )

