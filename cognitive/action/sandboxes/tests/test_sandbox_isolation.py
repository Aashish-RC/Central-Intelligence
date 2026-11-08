"""Unit tests for Sandbox filesystem isolation and ephemeral directory cleanup."""

from pathlib import Path
import pytest
from sandboxes.core.models import ExecutionRequest, SandboxStatus
from sandboxes.manager import SandboxManager


@pytest.fixture
def manager():
    return SandboxManager()


def test_virtual_files_and_ephemeral_cleanup(manager):
    # Pass virtual files that python script reads
    virtual_files = {
        "data/input.txt": "Pheonix Virtual Input",
        "config.json": '{"mode": "sandbox"}',
    }
    code = """
import json
with open('data/input.txt', 'r') as f:
    text = f.read().strip()
with open('config.json', 'r') as f:
    cfg = json.load(f)
print(f"READ: {text} | MODE: {cfg['mode']}")
"""
    req = ExecutionRequest(
        language="python",
        code=code,
        files=virtual_files,
    )
    result = manager.run(req)

    assert result.status == SandboxStatus.SUCCESS
    assert "READ: Pheonix Virtual Input | MODE: sandbox" in result.stdout
