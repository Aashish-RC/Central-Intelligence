"""Unit tests for MigrationRollbackGuard (Task 17.5)."""

import pytest
from platform.release.db.bytebase_adapter import SchemaMigration
from platform.release.migration.rollback_guard import (
    ActiveSession,
    MigrationPlan,
    MigrationRollbackGuard,
)


@pytest.fixture
def guard():
    return MigrationRollbackGuard()


def test_migration_breaking_active_sessions_is_blocked(guard: MigrationRollbackGuard):
    """Acceptance test: Migration that breaks active sessions is blocked."""
    # Active user session currently reading legacy_auth_token on user_sessions
    session_1 = ActiveSession(
        session_id="sess_live_101",
        schema_version="v1.2",
        accessed_tables={"user_sessions"},
        accessed_columns={"user_sessions.legacy_auth_token"},
    )
    session_2 = ActiveSession(
        session_id="sess_live_102",
        schema_version="v1.2",
        accessed_tables={"orders"},
        accessed_columns={"orders.total_amount"},
    )

    # Destructive migration dropping legacy_auth_token
    breaking_migration = SchemaMigration(
        migration_id="mig_drop_token_001",
        database_name="central_db",
        version="v1.3",
        title="Drop legacy auth tokens",
        up_sql="ALTER TABLE user_sessions DROP COLUMN legacy_auth_token;",
        down_sql="ALTER TABLE user_sessions ADD COLUMN legacy_auth_token TEXT;",
    )

    result = guard.validate(breaking_migration, active_sessions=[session_1, session_2])
    assert result.safe is False
    assert "Breaks session sess_live_101" in result.reason
    assert result.breaking_sessions == ["sess_live_101"]


def test_compatible_migration_passes(guard: MigrationRollbackGuard):
    """Additive, non-destructive migration passes validation safely."""
    session_1 = ActiveSession(
        session_id="sess_live_201",
        schema_version="v2.0",
        accessed_tables={"users"},
        accessed_columns={"users.email"},
    )

    safe_migration = SchemaMigration(
        migration_id="mig_add_column_002",
        database_name="central_db",
        version="v2.1",
        title="Add avatar url",
        up_sql="ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT NULL;",
        down_sql="ALTER TABLE users DROP COLUMN avatar_url;",
    )

    result = guard.validate(safe_migration, active_sessions=[session_1])
    assert result.safe is True
    assert "compatible" in result.reason
