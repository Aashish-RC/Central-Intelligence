"""Unit tests for Action Preview Renderer (5.27)."""

import pytest
from cognitive.action.safety.action_preview import ActionPreviewRenderer


def test_shell_preview_safe_and_destructive():
    # Safe command
    safe_prev = ActionPreviewRenderer.render_shell_preview("ls -la /tmp")
    assert safe_prev.action_type == "shell"
    assert safe_prev.danger_score < 0.5
    assert not safe_prev.requires_confirmation
    assert len(safe_prev.warnings) == 0

    # Destructive command
    danger_prev = ActionPreviewRenderer.render_shell_preview("rm -rf /var/log/*")
    assert danger_prev.danger_score >= 0.8
    assert danger_prev.requires_confirmation
    assert any("Destructive recursive deletion" in w for w in danger_prev.warnings)


def test_sql_preview_read_only_and_dangerous_mutation():
    # Read-only query
    ro_prev = ActionPreviewRenderer.render_sql_preview("SELECT * FROM users WHERE active = 1")
    assert ro_prev.metadata.get("is_read_only") is True
    assert not ro_prev.requires_confirmation

    # Unconstrained DELETE
    del_prev = ActionPreviewRenderer.render_sql_preview("DELETE FROM sessions")
    assert del_prev.danger_score >= 0.8
    assert del_prev.requires_confirmation
    assert any("missing WHERE clause" in w for w in del_prev.warnings)

    # DROP TABLE
    drop_prev = ActionPreviewRenderer.render_sql_preview("DROP TABLE accounts")
    assert drop_prev.danger_score >= 0.9
    assert any("Irreversible schema/table destruction" in w for w in drop_prev.warnings)


def test_file_write_diff_and_sensitive_file():
    old_code = "def add(a, b):\n    return a + b\n"
    new_code = "def add(a, b):\n    # Add numbers\n    return a + b\n"

    diff_prev = ActionPreviewRenderer.render_file_write_preview("math_utils.py", old_code, new_code)
    assert diff_prev.action_type == "file_write"
    assert "+    # Add numbers" in diff_prev.diff_content
    assert diff_prev.metadata["lines_added"] == 1
    assert not diff_prev.requires_confirmation

    # Sensitive .env file
    env_prev = ActionPreviewRenderer.render_file_write_preview(
        ".env", "", "SECRET_KEY=12345\nDB_PASS=secret"
    )
    assert env_prev.danger_score >= 0.8
    assert env_prev.requires_confirmation
    assert any("sensitive credential" in w for w in env_prev.warnings)


def test_api_call_preview_and_redaction():
    headers = {"Authorization": "Bearer secret_jwt_token_12345", "Content-Type": "application/json"}
    payload = {"username": "admin", "password": "super_secret_password", "role": "root"}

    prev = ActionPreviewRenderer.render_api_call_preview(
        "POST", "https://api.internal/v1/users", payload, headers
    )
    assert prev.action_type == "api_call"
    assert "secret_jwt_token_12345" not in prev.diff_content
    assert "super_secret_password" not in prev.diff_content
    assert "******** [REDACTED]" in prev.diff_content
