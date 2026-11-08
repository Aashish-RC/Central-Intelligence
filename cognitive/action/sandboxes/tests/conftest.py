"""Pytest fixtures and environment configuration for sandboxes tests."""

import os
import pytest


@pytest.fixture(autouse=True)
def setup_sandbox_test_env(monkeypatch, request):
    """Ensure SANDBOX_ALLOW_LOCAL=1 for tests unless explicitly disabled with @pytest.mark.disallow_local."""
    if "disallow_local" not in request.keywords:
        monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")
    else:
        monkeypatch.delenv("SANDBOX_ALLOW_LOCAL", raising=False)
