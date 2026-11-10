"""Unit tests for BytebaseAdapter (Task 17.4)."""

import pytest
from platform.release.db.bytebase_adapter import (
    BytebaseAdapter,
    MigrationStatus,
    ReviewStatus,
)


@pytest.fixture
def bytebase():
    return BytebaseAdapter()


def test_migration_lifecycle_create_review_apply_rollback(bytebase: BytebaseAdapter):
    """Acceptance test: Create migration, review, apply, rollback."""
    db = "central_postgres"
    v = "20261110_001"
    up_sql = "CREATE TABLE user_profiles (id UUID PRIMARY KEY, bio TEXT); CREATE INDEX idx_bio ON user_profiles(bio);"
    down_sql = "DROP TABLE user_profiles CASCADE;"

    # 1. Create migration
    mig = bytebase.create_migration(
        database_name=db,
        version=v,
        title="Add user profiles table",
        up_sql=up_sql,
        down_sql=down_sql,
    )
    assert mig.review_status == ReviewStatus.PENDING_REVIEW
    assert mig.execution_status == MigrationStatus.PENDING

    # 2. Applying without approval fails gate
    with pytest.raises(PermissionError, match="requires 'approved'"):
        bytebase.apply_migration(mig.migration_id)

    # 3. Review and approve
    reviewed = bytebase.review_migration(mig.migration_id, approved=True, reviewer="lead_dba")
    assert reviewed.review_status == ReviewStatus.APPROVED
    assert reviewed.reviewer == "lead_dba"

    # 4. Apply migration
    applied = bytebase.apply_migration(mig.migration_id)
    assert applied.execution_status == MigrationStatus.APPLIED
    assert len(applied.applied_statements) == 2
    assert bytebase.is_version_applied(db, v) is True

    # 5. Rollback migration
    rolled_back = bytebase.rollback_migration(mig.migration_id)
    assert rolled_back.execution_status == MigrationStatus.ROLLED_BACK
    assert bytebase.is_version_applied(db, v) is False

