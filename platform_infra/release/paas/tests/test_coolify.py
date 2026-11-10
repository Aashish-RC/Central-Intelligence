"""Unit tests for CoolifyAdapter (Task 17.1)."""

import pytest
from platform_infra.release.paas.coolify_adapter import (
    CoolifyAdapter,
    CoolifyConfig,
    DeploymentStatus,
)


@pytest.fixture
def coolify():
    return CoolifyAdapter(config=CoolifyConfig(use_mock=True))


def test_deploy_service_via_git_push(coolify: CoolifyAdapter):
    """Acceptance test: Can deploy a service via git push."""
    app_id = "agent-gateway-service"
    commit_sha = "a1b2c3d4e5f6"

    coolify.register_application(
        app_id=app_id,
        name="Agent Gateway",
        git_repository="git@github.com:central-intelligence/agent-gateway.git",
        git_branch="main",
    )

    result = coolify.deploy_via_git_push(
        app_id=app_id,
        commit_sha=commit_sha,
        branch="main",
    )

    assert result.status == DeploymentStatus.FINISHED
    assert result.commit_sha == commit_sha
    assert result.ssl_enabled is True
    assert result.url is not None
    assert any("Let's Encrypt SSL" in log for log in result.build_logs)

    # Status lookup
    status = coolify.get_deployment_status(result.deployment_uuid)
    assert status is not None
    assert status.status == DeploymentStatus.FINISHED


def test_deploy_and_rollback(coolify: CoolifyAdapter):
    """Deploy v1, deploy v2, then rollback restores v1."""
    app_id = "perception-service"

    coolify.deploy_via_git_push(app_id, commit_sha="commit_v1")
    coolify.deploy_via_git_push(app_id, commit_sha="commit_v2")

    rb = coolify.rollback(app_id)
    assert rb.status == DeploymentStatus.ROLLED_BACK
    assert rb.commit_sha == "commit_v1"

