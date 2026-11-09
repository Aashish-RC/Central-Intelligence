"""Unit tests for Feature 5.33: Sandbox Resource Limits & Dynamic Quota Enforcement."""

import pytest
from sandboxes.core.models import ExecutionRequest, ResourceLimits, SandboxStatus
from sandboxes.governor.security_governor import (
    SecurityGovernor,
    MAX_ALLOWED_TIMEOUT_SECONDS,
    MAX_ALLOWED_MEMORY_MB,
    MAX_ALLOWED_OUTPUT_BYTES,
)
from sandboxes.manager import SandboxManager


@pytest.fixture
def governor():
    return SecurityGovernor()


@pytest.fixture
def manager():
    return SandboxManager()


def test_resource_limits_timeout_hard_ceiling(governor):
    req = ExecutionRequest(
        code="print('hello')",
        limits=ResourceLimits(timeout_seconds=MAX_ALLOWED_TIMEOUT_SECONDS + 50.0),
    )
    is_valid, err = governor.validate_request(req)
    assert not is_valid
    assert "timeout_seconds" in err
    assert "exceeds hard ceiling" in err


def test_resource_limits_negative_timeout(governor):
    req = ExecutionRequest(
        code="print('hello')",
        limits=ResourceLimits(timeout_seconds=-1.0),
    )
    is_valid, err = governor.validate_request(req)
    assert not is_valid
    assert "timeout_seconds must be positive" in err


def test_resource_limits_memory_hard_ceiling(governor):
    req = ExecutionRequest(
        code="print('hello')",
        limits=ResourceLimits(max_memory_mb=MAX_ALLOWED_MEMORY_MB + 1024),
    )
    is_valid, err = governor.validate_request(req)
    assert not is_valid
    assert "max_memory_mb" in err
    assert "exceeds hard ceiling" in err


def test_files_count_quota_enforced(governor):
    files = {f"file_{i}.txt": f"data {i}" for i in range(105)}
    req = ExecutionRequest(
        code="print('ok')",
        files=files,
        limits=ResourceLimits(max_files_count=100),
    )
    is_valid, err = governor.validate_request(req)
    assert not is_valid
    assert "Files count" in err
    assert "exceeds allowed limit" in err


def test_file_size_quota_enforced(governor):
    large_payload = "X" * (11 * 1024 * 1024)  # 11MB
    req = ExecutionRequest(
        code="print('ok')",
        files={"large.bin": large_payload},
        limits=ResourceLimits(max_file_size_bytes=10 * 1024 * 1024),
    )
    is_valid, err = governor.validate_request(req)
    assert not is_valid
    assert "exceeds individual size limit" in err


def test_fork_bomb_pattern_blocked(governor):
    req = ExecutionRequest(
        code="import os\nos.fork()\nprint('forked')",
    )
    is_valid, err = governor.validate_request(req)
    assert not is_valid
    assert "os" in err and "fork" in err
