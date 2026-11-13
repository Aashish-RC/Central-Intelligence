"""Pytest fixtures and environment configuration for sandboxes tests."""

import os
import pytest


@pytest.fixture
def test_trusted_context(monkeypatch):
    """Provide a validated TrustedExecutionContext for authorized unit test fixtures."""
    monkeypatch.setenv("CENTRAL_TRUSTED_HOST_TOKEN", "ci-fixture-token")
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "development")
    from sandboxes.trusted_host import TrustedExecutionContext
    return TrustedExecutionContext(
        caller_id="test_runner",
        auth_token="ci-fixture-token",
        capability="TEST_FIXTURE_EXECUTION",
        purpose="unit-test-fixtures",
    )
