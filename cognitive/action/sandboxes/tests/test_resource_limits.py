"""Unit tests for resource limits: timeout containment and output size bounds."""

import pytest
from sandboxes.core.models import ExecutionRequest, ResourceLimits, SandboxStatus
from sandboxes.manager import SandboxManager


@pytest.fixture
def manager():
    return SandboxManager()


def test_timeout_containment(manager):
    # Code that attempts to run for 2.0s with 0.2s limit
    code = "import time\ntime.sleep(2.0)\nprint('Done sleeping')"
    req = ExecutionRequest(
        language="python",
        code=code,
        limits=ResourceLimits(timeout_seconds=0.2),
    )
    result = manager.run(req)

    assert result.status == SandboxStatus.TIMEOUT
    assert result.exit_code == -1
    assert "timed out" in result.stderr.lower()


def test_output_size_truncation(manager):
    # Code generating large output
    code = "print('A' * 20000)"
    req = ExecutionRequest(
        language="python",
        code=code,
        limits=ResourceLimits(max_output_bytes=1000),
    )
    result = manager.run(req)

    assert result.status == SandboxStatus.SUCCESS
    assert len(result.stdout) < 20000
    assert "TRUNCATED BY SANDBOX" in result.stdout
