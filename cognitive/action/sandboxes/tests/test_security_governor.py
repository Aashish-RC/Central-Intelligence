"""Unit tests for SecurityGovernor: pattern blocking, network gating, and env sanitization."""

import pytest
from sandboxes.core.models import ExecutionRequest, ResourceLimits
from sandboxes.governor.security_governor import SecurityGovernor


@pytest.fixture
def governor():
    return SecurityGovernor()


def test_block_prohibited_libraries(governor):
    req = ExecutionRequest(code="import ctypes\nctypes.windll.kernel32")
    is_valid, err = governor.validate_request(req)
    assert not is_valid
    assert "ctypes" in err


def test_block_sensitive_file_access(governor):
    req = ExecutionRequest(code="with open('/etc/shadow') as f: data = f.read()")
    is_valid, err = governor.validate_request(req)
    assert not is_valid
    assert "shadow" in err


def test_network_access_gating(governor):
    # Network disabled by default
    req_no_net = ExecutionRequest(
        code="import socket\ns = socket.socket()",
        limits=ResourceLimits(network_access=False),
    )
    is_valid, err = governor.validate_request(req_no_net)
    assert not is_valid
    assert "Network access is disabled" in err

    # Network explicitly allowed
    req_with_net = ExecutionRequest(
        code="import socket\ns = socket.socket()",
        limits=ResourceLimits(network_access=True),
    )
    is_valid, err = governor.validate_request(req_with_net)
    assert is_valid
    assert err is None


def test_path_traversal_detection(governor):
    req = ExecutionRequest(
        code="print('ok')",
        files={"../../escaped.txt": "evil content"},
    )
    is_valid, err = governor.validate_request(req)
    assert not is_valid
    assert "Path traversal attempt" in err


def test_environment_sanitization(governor):
    allowed = ["PATH", "SYSTEMROOT"]
    custom = {"USER_SETTING": "123", "SAFE_VAR": "hello"}
    env = governor.sanitize_environment(allowed, custom)

    assert "PATH" in env or "SYSTEMROOT" in env
    assert env.get("USER_SETTING") == "123"
    assert env.get("SAFE_VAR") == "hello"

    # Verify no leaked secret keys
    for k in env.keys():
        assert "SECRET" not in k.upper() or k in custom


def test_block_destructive_commands(governor):
    destructive = [
        "rm -rf /",
        "rm -rf --no-preserve-root",
        ":(){ :|:& };:",
        "mkfs -t ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        "chmod -R 777 /",
    ]
    for cmd in destructive:
        req = ExecutionRequest(code=f"# Do damage\n{cmd}")
        is_valid, err = governor.validate_request(req)
        assert not is_valid, f"Expected {cmd} to be blocked"
        assert "blocked by sandbox security policy" in err.lower()


def test_block_windows_registry_and_vault_tampering(governor):
    tamper_patterns = [
        "cat /etc/passwd",
        "open('C:\\Windows\\System32\\config\\SAM')",
        "read_file('.vault_key')",
    ]
    for code in tamper_patterns:
        req = ExecutionRequest(code=code)
        is_valid, err = governor.validate_request(req)
        assert not is_valid, f"Expected {code} to be blocked"
        assert "violates security policy" in err.lower()


def test_sensitive_env_stripping(governor, monkeypatch):
    monkeypatch.setenv("PHEONIX_SECRET_TOKEN", "supersecret123")
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@localhost:5432/db")
    
    allowed = ["PATH", "PHEONIX_SECRET_TOKEN", "DATABASE_URL"]
    custom = {"SAFE_PARAM": "1"}
    sanitized = governor.sanitize_environment(allowed, custom)
    
    assert "PHEONIX_SECRET_TOKEN" not in sanitized
    assert "DATABASE_URL" not in sanitized
    assert sanitized["SAFE_PARAM"] == "1"

