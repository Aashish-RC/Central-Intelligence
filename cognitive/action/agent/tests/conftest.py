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
    action_dir / "sandboxes",
    action_dir,
    cognitive_dir / "memory" / "storage",
    cognitive_dir / "memory",
    cognitive_dir,
    root_dir,
]:
    if p.exists():
        p_str = str(p)
        while p_str in sys.path:
            sys.path.remove(p_str)
        sys.path.insert(0, p_str)


@pytest.fixture(autouse=True)
def enable_sandbox_local(monkeypatch, request):
    """Enable SANDBOX_ALLOW_LOCAL=1 for agent tests by default."""
    if "disallow_local" not in request.keywords:
        monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")

