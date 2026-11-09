"""Unit tests for Review-Before-Wider-Sharing Pipeline (5.47, 19.35)."""

import pytest
from cognitive.action.safety.sharing_pipeline import (
    ReviewSharingPipeline,
    SharingScope,
    SharingStatus,
)


def test_clean_team_internal_auto_approval():
    pipeline = ReviewSharingPipeline(auto_approve_clean_team_internal=True)
    req = pipeline.submit_for_sharing(
        artifact_id="art_101",
        content="Here are the public quarterly benchmarks for Q3.",
        source_agent_id="analyst_agent",
        target_scope=SharingScope.TEAM_INTERNAL,
    )

    assert req.status == SharingStatus.APPROVED
    assert req.reviewer_id == "system:auto_approver"
    assert len(req.redactions_applied) == 0


def test_sensitive_asset_requires_supervisor_review():
    pipeline = ReviewSharingPipeline()
    raw_content = "Connect to database with api_key='sk-test-live-999948271829' or email admin@company.internal."
    req = pipeline.submit_for_sharing(
        artifact_id="art_102",
        content=raw_content,
        source_agent_id="agent_junior",
        target_scope=SharingScope.CROSS_TEAM,
    )

    # Requires human review due to cross-team scope and detected sensitive tokens
    assert req.status == SharingStatus.REVIEW_PENDING
    assert len(req.redactions_applied) >= 2
    assert "sk-test-live" not in req.sanitized_content
    assert "[REDACTED_SECRET_KEY]" in req.sanitized_content
    assert "[REDACTED_EMAIL_PII]" in req.sanitized_content

    # Supervisor approves with sanitized version
    reviewed = pipeline.review_request(
        req.request_id,
        reviewer_id="supervisor_bob",
        approve=True,
        notes="Approved with automated redactions",
        use_sanitized=True,
    )
    assert reviewed.status == SharingStatus.REDACTED_APPROVED
    assert reviewed.reviewer_id == "supervisor_bob"


def test_supervisor_rejection():
    pipeline = ReviewSharingPipeline()
    req = pipeline.submit_for_sharing(
        artifact_id="art_103",
        content="Credit card 4111-2222-3333-4444 found in memory log",
        source_agent_id="agent_junior",
        target_scope=SharingScope.PUBLIC,
    )

    assert req.status == SharingStatus.REVIEW_PENDING

    # Supervisor rejects
    rejected = pipeline.review_request(
        req.request_id,
        reviewer_id="supervisor_bob",
        approve=False,
        notes="Financial card data cannot be promoted publicly",
    )
    assert rejected.status == SharingStatus.REJECTED
    assert rejected.decision_notes == "Financial card data cannot be promoted publicly"
