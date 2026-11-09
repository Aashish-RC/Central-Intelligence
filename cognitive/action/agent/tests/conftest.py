"""Pytest fixtures for agent tests."""

import sys
from pathlib import Path
import pytest

# Ensure central-intelligence paths are in sys.path
agent_tests_dir = Path(__file__).resolve().parent
agent_dir = agent_tests_dir.parent
action_dir = agent_dir.parent
cognitive_dir = action_dir.parent
root_dir = cognitive_dir.parent

for p in [
    root_dir,
    cognitive_dir,
    cognitive_dir / "memory",
    cognitive_dir / "memory" / "storage",
    action_dir,
    action_dir / "sandboxes",
    agent_dir,
]:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))


@pytest.fixture(autouse=True)
def enable_sandbox_local(monkeypatch, request):
    """Enable SANDBOX_ALLOW_LOCAL=1 for agent tests by default."""
    if "disallow_local" not in request.keywords:
        monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")

