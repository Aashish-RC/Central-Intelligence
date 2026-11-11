"""Tests for L17 Migration Dry-Run Runner."""

from platform_infra.release.db.bytebase_adapter import BytebaseAdapter, MigrationStatus
from platform_infra.release.migration.dry_run import MigrationDryRunner
from platform_infra.release.migration.rollback_guard import ActiveSession


def test_dry_run_predicts_changes_without_applying():
    bb = BytebaseAdapter()
    runner = MigrationDryRunner(bytebase=bb)

    mig = bb.create_migration(
        database_name="core_db",
        version="v2026_02",
        title="Add memory tags and drop legacy column",
        up_sql="ALTER TABLE memories ADD COLUMN tag TEXT; ALTER TABLE memories DROP COLUMN legacy_blob;",
        down_sql="ALTER TABLE memories DROP COLUMN tag;",
    )
    sessions = [ActiveSession(session_id="sess_1", schema_version="v2026_01", accessed_columns={"memories.legacy_blob"})]

    report = runner.dry_run(mig, active_sessions=sessions)
    assert report.statements_analyzed == 2
    assert report.is_destructive is True
    assert report.has_down_sql is True
    assert report.session_validation is not None
    assert report.session_validation.safe is False
    assert "sess_1" in report.session_validation.breaking_sessions
    # Live state must remain untouched
    assert mig.execution_status == MigrationStatus.PENDING
    assert bb.is_version_applied("core_db", "v2026_02") is False
    assert report.applied_to_live is False
