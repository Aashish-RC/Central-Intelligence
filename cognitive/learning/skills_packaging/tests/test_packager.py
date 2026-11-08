"""Tests for Packager."""

import pytest
from skills_packaging.core.models import (
    PackageType,
    PluginManifest,
    SkillManifest,
)
from skills_packaging.packaging.packager import Packager


@pytest.fixture
def packager():
    return Packager()


def test_package_valid_skill(packager):
    manifest = SkillManifest(
        skill_id="python-linter",
        name="Python Linter Skill",
        version="1.0.0",
        description="Lints Python AST",
        entrypoint="lint.py",
        required_tools=["code_interpreter"],
    )
    files = {
        "lint.py": "def lint(): return True",
        "README.md": "# Python Linter",
    }

    bundle = packager.package_skill(manifest, files)
    assert bundle.package_type == PackageType.SKILL
    assert bundle.package_id == "python-linter"
    assert bundle.version == "1.0.0"
    assert len(bundle.sha256_checksum) == 64
    assert "lint.py" in bundle.files


def test_package_skill_missing_entrypoint(packager):
    manifest = SkillManifest(
        skill_id="bad-skill",
        name="Bad Skill",
        version="0.1.0",
        description="Missing entrypoint file",
        entrypoint="non_existent.py",
    )
    files = {"other.py": "x = 1"}

    with pytest.raises(ValueError, match="missing from file package"):
        packager.package_skill(manifest, files)


def test_package_skill_invalid_semver(packager):
    manifest = SkillManifest(
        skill_id="bad-ver",
        name="Bad Ver",
        version="v1_0_beta",
        description="Invalid version string",
        entrypoint="main.py",
    )
    with pytest.raises(ValueError, match="Invalid SemVer format"):
        packager.package_skill(manifest, {"main.py": "print(1)"})


def test_package_valid_plugin(packager):
    skill_a = SkillManifest(
        skill_id="sub-a",
        name="Sub A",
        version="0.1.0",
        description="Part of bundle",
        entrypoint="a.py",
    )
    plugin_manifest = PluginManifest(
        plugin_id="developer-toolkit",
        name="Dev Toolkit Plugin",
        version="1.2.0",
        description="Bundle of developer skills",
        bundled_skills=[skill_a],
        mcp_servers=["mcp-sqlite"],
        rules=["rule_deny_secret_leakage"],
    )
    files = {
        "a.py": "def run_a(): pass",
        "config.json": '{"mode": "fast"}',
    }

    bundle = packager.package_plugin(plugin_manifest, files)
    assert bundle.package_type == PackageType.PLUGIN
    assert bundle.package_id == "developer-toolkit"
    assert len(bundle.sha256_checksum) == 64
