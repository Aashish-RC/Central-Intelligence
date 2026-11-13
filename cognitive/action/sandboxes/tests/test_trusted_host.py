"""Unit tests for TrustedHostExecutionPolicy and TrustedHostProcessRunner."""

import os
import pytest
from sandboxes.trusted_host import (
    TrustedExecutionContext,
    TrustedHostExecutionError,
    TrustedHostExecutionPolicy,
    TrustedHostProcessRunner,
    TRUSTED_HOST_TOKEN_ENV,
)


@pytest.fixture
def valid_token_env(monkeypatch):
    token = "sec-token-12345"
    monkeypatch.setenv(TRUSTED_HOST_TOKEN_ENV, token)
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "development")
    return token


def test_trusted_host_policy_validates_legitimate_context(valid_token_env):
    policy = TrustedHostExecutionPolicy()
    ctx = TrustedExecutionContext(
        caller_id="orchestrator",
        capability="SYSTEM_DIAGNOSTIC",
        auth_token=valid_token_env,
        purpose="check-system-health",
    )
    # Should not raise
    policy.validate_context(ctx)


def test_trusted_host_policy_rejects_in_production(valid_token_env, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    policy = TrustedHostExecutionPolicy()
    ctx = TrustedExecutionContext(
        caller_id="orchestrator",
        capability="SYSTEM_DIAGNOSTIC",
        auth_token=valid_token_env,
    )
    with pytest.raises(TrustedHostExecutionError) as exc_info:
        policy.validate_context(ctx)
    assert "strictly forbidden in production" in str(exc_info.value)


@pytest.mark.parametrize("caller", ["agent", "untrusted", "llm", "tool", "prompt", "user_input", "external"])
def test_trusted_host_policy_rejects_untrusted_caller_identifiers(valid_token_env, caller):
    policy = TrustedHostExecutionPolicy()
    ctx = TrustedExecutionContext(
        caller_id=caller,
        capability="SYSTEM_DIAGNOSTIC",
        auth_token=valid_token_env,
    )
    with pytest.raises(TrustedHostExecutionError) as exc_info:
        policy.validate_context(ctx)
    assert "Untrusted agent execution cannot access or be promoted" in str(exc_info.value)


def test_trusted_host_policy_rejects_invalid_token(valid_token_env):
    policy = TrustedHostExecutionPolicy()
    ctx = TrustedExecutionContext(
        caller_id="orchestrator",
        capability="SYSTEM_DIAGNOSTIC",
        auth_token="wrong-token",
    )
    with pytest.raises(TrustedHostExecutionError) as exc_info:
        policy.validate_context(ctx)
    assert "Invalid auth_token in TrustedExecutionContext" in str(exc_info.value)


def test_trusted_host_policy_rejects_unauthorized_capability(valid_token_env):
    policy = TrustedHostExecutionPolicy()
    ctx = TrustedExecutionContext(
        caller_id="orchestrator",
        capability="ARBITRARY_SHELL_EXEC",
        auth_token=valid_token_env,
    )
    with pytest.raises(TrustedHostExecutionError) as exc_info:
        policy.validate_context(ctx)
    assert "Unauthorized capability 'ARBITRARY_SHELL_EXEC'" in str(exc_info.value)


def test_trusted_host_process_runner_executes_argv(valid_token_env):
    runner = TrustedHostProcessRunner()
    ctx = TrustedExecutionContext(
        caller_id="orchestrator",
        capability="SYSTEM_DIAGNOSTIC",
        auth_token=valid_token_env,
    )
    res = runner.execute_trusted_command(command_argv=["python3", "-c", "print('audited-ok')"], context=ctx)
    assert res.exit_code == 0
    assert "audited-ok" in res.stdout
    assert len(runner.policy.get_audit_log()) == 1
    assert runner.policy.get_audit_log()[0].success is True
    assert runner.policy.get_audit_log()[0].caller_id == "orchestrator"


def test_trusted_host_process_runner_audits_failure(valid_token_env):
    runner = TrustedHostProcessRunner()
    ctx = TrustedExecutionContext(
        caller_id="orchestrator",
        capability="SYSTEM_DIAGNOSTIC",
        auth_token=valid_token_env,
    )
    res = runner.execute_trusted_command(command_argv=["python3", "-c", "import sys; sys.exit(42)"], context=ctx)
    assert res.exit_code == 42
    assert len(runner.policy.get_audit_log()) == 1
    assert runner.policy.get_audit_log()[0].success is False
    assert runner.policy.get_audit_log()[0].exit_code == 42


def test_trusted_host_process_runner_rejects_empty_argv(valid_token_env):
    runner = TrustedHostProcessRunner()
    ctx = TrustedExecutionContext(
        caller_id="orchestrator",
        capability="SYSTEM_DIAGNOSTIC",
        auth_token=valid_token_env,
    )
    with pytest.raises(TrustedHostExecutionError) as exc_info:
        runner.execute_trusted_command(command_argv=[], context=ctx)
    assert "command_argv must be a non-empty sequence" in str(exc_info.value)
