"""Pytest fixtures for agent tests."""

import pytest


@pytest.fixture(autouse=True)
def enable_sandbox_local(monkeypatch, request):
    """Enable SANDBOX_ALLOW_LOCAL=1 for agent tests by default."""
    if "disallow_local" not in request.keywords:
        monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")
