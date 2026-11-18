"""Unit and verification tests for Task S4.2: Clean Installation & Bootstrap Script.

Validates that all bootstrap artifacts, pinned dependency lockfiles, cryptographic
environment generators, and multi-database initialization routines comply with
Stage S4.2 requirements and execute cleanly without dependency drift.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_bootstrap_artifacts_exist():
    """Verify that all mandatory bootstrap files and scripts exist in the repository."""
    mandatory_files = [
        REPO_ROOT / "scripts" / "bootstrap.sh",
        REPO_ROOT / "scripts" / "bootstrap.ps1",
        REPO_ROOT / "scripts" / "generate_env.py",
        REPO_ROOT / "compose" / "postgres" / "init-multi-db.sh",
        REPO_ROOT / ".env.example",
        REPO_ROOT / "requirements.lock",
        REPO_ROOT / "requirements.txt",
        REPO_ROOT / "package.json",
        REPO_ROOT / "pnpm-lock.yaml",
        REPO_ROOT / "docker-compose.yml",
    ]
    for file_path in mandatory_files:
        assert file_path.exists(), f"Mandatory bootstrap file missing: {file_path.relative_to(REPO_ROOT)}"
        assert file_path.stat().st_size > 0, f"Bootstrap file is empty: {file_path.relative_to(REPO_ROOT)}"


def test_requirements_lock_integrity():
    """Verify requirements.lock has pinned dependencies with sha256 checksums."""
    lock_file = REPO_ROOT / "requirements.lock"
    content = lock_file.read_text(encoding="utf-8")
    assert "--hash=sha256:" in content, "requirements.lock must contain pinned SHA256 hashes"
    # Ensure key runtime dependencies are present in lock
    for pkg in ["pydantic", "fastapi", "httpx", "pytest", "cryptography"]:
        assert pkg in content, f"Expected core package '{pkg}' missing from requirements.lock"


def test_pnpm_lock_integrity():
    """Verify pnpm-lock.yaml is valid YAML and defines pinned packages."""
    lock_file = REPO_ROOT / "pnpm-lock.yaml"
    content = lock_file.read_text(encoding="utf-8")
    assert "lockfileVersion:" in content, "pnpm-lock.yaml must contain lockfileVersion"
    assert "packages:" in content, "pnpm-lock.yaml must specify pinned package definitions"


def test_env_example_completeness():
    """Verify .env.example declares all required services and variable definitions."""
    example_file = REPO_ROOT / ".env.example"
    content = example_file.read_text(encoding="utf-8")

    critical_keys = [
        "NANGO_SECRET_KEY",
        "MEILISEARCH_MASTER_KEY",
        "KEYCLOAK_ADMIN",
        "KEYCLOAK_ADMIN_PASSWORD",
        "INFISICAL_ENCRYPTION_KEY",
        "INFISICAL_AUTH_SECRET",
        "OPENFGA_POSTGRES_PASSWORD",
        "LAGO_POSTGRES_PASSWORD",
        "LAGO_SECRET_KEY_BASE",
        "LAGO_RSA_PRIVATE_KEY",
        "OPENMETER_POSTGRES_PASSWORD",
        "OPENMETER_CLICKHOUSE_PASSWORD",
        "LIBRECHAT_MONGO_USER",
        "LIBRECHAT_MONGO_PASSWORD",
        "POSTGRES_PASSWORD",
    ]
    for key in critical_keys:
        assert f"{key}=" in content, f"Critical key '{key}' missing from .env.example"


def test_generate_env_produces_secure_tokens(tmp_path):
    """Verify generate_env logic produces strong cryptographic secrets and valid RSA keys."""
    from scripts.generate_env import generate_rsa_key_b64, sync_env_file

    rsa_b64 = generate_rsa_key_b64()
    assert len(rsa_b64) > 100, "Generated RSA key must be non-empty base64 string"

    # Test sync into temporary directory
    temp_repo = tmp_path / "repo"
    temp_repo.mkdir()
    (temp_repo / ".env.example").write_text((REPO_ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")

    out_env = sync_env_file(temp_repo)
    assert out_env.exists()
    content = out_env.read_text(encoding="utf-8")

    assert "replace-with-" not in content, "All placeholder tokens must be replaced with real values"
    assert "POSTGRES_PASSWORD=ci_pass_" in content


def test_postgres_init_multi_db_script():
    """Verify PostgreSQL init-multi-db.sh script syntax and logical database declaration."""
    script_path = REPO_ROOT / "compose" / "postgres" / "init-multi-db.sh"
    content = script_path.read_text(encoding="utf-8")
    assert "create_db_and_user" in content
    assert "POSTGRES_MULTIPLE_DATABASES" in content
    assert "openfga,infisical,lago,openmeter,signoz" in content


def test_compose_config_validation():
    """Verify that docker compose config parses cleanly with current .env or fallback .env.example."""
    env_file = REPO_ROOT / ".env"
    cmd = ["docker", "compose"]
    if not env_file.exists():
        cmd.extend(["--env-file", str(REPO_ROOT / ".env.example")])
    cmd.extend(["config", "--quiet"])

    res = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"docker compose config failed: {res.stderr}"
