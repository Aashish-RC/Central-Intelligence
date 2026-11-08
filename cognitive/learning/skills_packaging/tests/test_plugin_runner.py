"""Tests for PluginRunner."""

import pytest
from skills_packaging.core.models import (
    InstallationRecord,
    PackageType,
    PluginManifest,
    SkillManifest,
)
from skills_packaging.packaging.installer import Installer
from skills_packaging.packaging.packager import Packager
from skills_packaging.runtime.plugin_runner import PluginRunner


@pytest.fixture
def runner():
    return PluginRunner()


def test_execute_skill(runner, tmp_path):
    packager = Packager()
    installer = Installer()

    manifest = SkillManifest(
        skill_id="calculator-skill",
        name="Calculator",
        version="1.0.0",
        description="Math ops",
        entrypoint="calc.py",
    )
    bundle = packager.package_skill(manifest, {"calc.py": "def add(a, b): return a + b"})
    record = installer.install_package(bundle, str(tmp_path / "exts"))

    res = runner.execute_skill(record, "calculate: 2 + 2")
    assert res.status == "completed"
    assert "calculator-skill" in res.output
    assert res.duration_ms >= 0.0


def test_execute_plugin(runner, tmp_path):
    packager = Packager()
    installer = Installer()

    sub_skill = SkillManifest(
        skill_id="ast-scanner",
        name="AST Scanner",
        version="0.1.0",
        description="Scans AST",
        entrypoint="scan.py",
    )
    plugin_manifest = PluginManifest(
        plugin_id="code-intel-plugin",
        name="Code Intelligence",
        version="1.0.0",
        description="Code intelligence toolkit",
        bundled_skills=[sub_skill],
    )
    bundle = packager.package_plugin(
        plugin_manifest,
        {"scan.py": "def scan(): return []", "README.md": "docs"},
    )
    record = installer.install_package(bundle, str(tmp_path / "exts"))

    res = runner.execute_plugin(record, target_skill="ast-scanner", payload="scan main.py")
    assert res.status == "completed"
    assert "code-intel-plugin" in res.output
    assert "ast-scanner" in res.output


def test_execute_deactivated_package_raises(runner):
    inactive_record = InstallationRecord(
        package_id="disabled-skill",
        package_type=PackageType.SKILL,
        version="1.0.0",
        install_dir="/tmp/does-not-matter",
        is_active=False,
        checksum="abcd",
    )
    with pytest.raises(RuntimeError, match="is deactivated or uninstalled"):
        runner.execute_skill(inactive_record, "run")
