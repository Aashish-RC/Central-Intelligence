"""Tests for L17 automatic changelog generator."""

from platform_infra.release.changelog.generator import (
    ChangelogGenerator,
    CommitEntry,
    SchemaDiffEntry,
)


def test_generate_v1_2_3_changelog_with_commits_and_schema_diffs():
    gen = ChangelogGenerator()
    commits = [
        CommitEntry.from_raw("abc123456", "feat(L15): add event bus with durable queues"),
        CommitEntry.from_raw("def678901", "fix(L16): handle regional failover cooldown"),
        CommitEntry.from_raw("999aaabbb", "feat(gateway)!: drop legacy v1 auth header"),
    ]
    diffs = [
        SchemaDiffEntry(table="audit_events", change_type="ADD_COLUMN", detail="added tenant_region TEXT"),
    ]
    release = gen.generate("v1.2.3", commits=commits, schema_diffs=diffs, release_date="2026-11-11")

    assert release.version == "v1.2.3"
    assert "## [v1.2.3] - 2026-11-11" in release.markdown
    assert "### Features" in release.markdown
    assert "### Bug Fixes" in release.markdown
    assert "### Breaking Changes" in release.markdown
    assert "### Schema Changes" in release.markdown
    assert "audit_events" in release.markdown

