"""End-to-End Tests for Skills and Plugin Packaging: Verifies that a skill and a plugin install and run."""

import pytest
from skills_packaging.core.models import (
    PluginManifest,
    SkillManifest,
)
from skills_packaging.packaging.installer import Installer
from skills_packaging.packaging.packager import Packager
from skills_packaging.runtime.plugin_runner import PluginRunner


def test_skill_and_plugin_install_and_run(tmp_path):
    """Core Done When Criteria: A skill and a plugin install and run."""
    packager = Packager()
    installer = Installer()
    runner = PluginRunner()

    destination_root = str(tmp_path / "installed_extensions")

    # -------------------------------------------------------------
    # 1. VERIFY SKILL: Package, Install, and Run
    # -------------------------------------------------------------
    skill_manifest = SkillManifest(
        skill_id="sec-scanner-skill",
        name="Security Vulnerability Scanner",
        version="1.0.0",
        description="Static security analyzer for secret leaks and CVEs",
        entrypoint="scanner.py",
        required_tools=["code_interpreter", "grep_search"],
    )
    skill_files = {
        "scanner.py": "def scan_repo(): return {'vulnerabilities': 0}",
        "config.yaml": "rules: ['cve', 'secrets']",
    }

    # Package Skill
    skill_bundle = packager.package_skill(skill_manifest, skill_files)
    assert skill_bundle.sha256_checksum is not None

    # Install Skill
    skill_record = installer.install_package(skill_bundle, destination_root)
    assert skill_record.is_active is True
    assert (tmp_path / "installed_extensions" / "sec-scanner-skill" / "scanner.py").exists()

    # Run Skill
    skill_exec = runner.execute_skill(skill_record, payload="target_path=/src")
    assert skill_exec.status == "completed"
    assert "sec-scanner-skill" in skill_exec.output
    assert "Success" in skill_exec.output

    # -------------------------------------------------------------
    # 2. VERIFY PLUGIN: Package, Install, and Run
    # -------------------------------------------------------------
    sub_skill_a = SkillManifest(
        skill_id="git-hook-analyzer",
        name="Git Hook Analyzer",
        version="0.1.0",
        description="Analyzes pre-commit hooks",
        entrypoint="hooks.py",
    )
    plugin_manifest = PluginManifest(
        plugin_id="devtools-suite-plugin",
        name="Developer Tools Suite",
        version="2.0.0",
        description="Integrated developer suite containing git tools and MCP connectors",
        bundled_skills=[sub_skill_a],
        mcp_servers=["mcp-git-server"],
        rules=["rule_deny_secret_leakage"],
    )
    plugin_files = {
        "hooks.py": "def verify_hooks(): return True",
        "mcp_config.json": '{"server": "git"}',
    }

    # Package Plugin
    plugin_bundle = packager.package_plugin(plugin_manifest, plugin_files)
    assert plugin_bundle.sha256_checksum is not None

    # Install Plugin
    plugin_record = installer.install_package(plugin_bundle, destination_root)
    assert plugin_record.is_active is True
    assert (tmp_path / "installed_extensions" / "devtools-suite-plugin" / "hooks.py").exists()

    # Run Plugin
    plugin_exec = runner.execute_plugin(
        plugin_record, target_skill="git-hook-analyzer", payload="git_commit_hash=abc1234"
    )
    assert plugin_exec.status == "completed"
    assert "devtools-suite-plugin" in plugin_exec.output
    assert "git-hook-analyzer" in plugin_exec.output
    assert "Success" in plugin_exec.output
