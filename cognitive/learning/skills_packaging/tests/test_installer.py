"""Tests for Installer."""

import pytest
from skills_packaging.core.models import (
    PackageBundle,
    PackageType,
    SkillManifest,
)
from skills_packaging.packaging.installer import Installer
from skills_packaging.packaging.packager import Packager


@pytest.fixture
def installer():
    return Installer()


@pytest.fixture
def sample_bundle():
    packager = Packager()
    manifest = SkillManifest(
        skill_id="test-formatter",
        name="Formatter",
        version="0.2.1",
        description="Code formatting tool",
        entrypoint="fmt.py",
    )
    files = {"fmt.py": "def format_code(): return 'formatted'"}
    return packager.package_skill(manifest, files)


def test_install_package_clean(installer, sample_bundle, tmp_path):
    dest = str(tmp_path / "installed_exts")
    record = installer.install_package(sample_bundle, dest)

    assert record.package_id == "test-formatter"
    assert record.is_active is True
    assert record.checksum == sample_bundle.sha256_checksum

    # Verify files on disk
    installed_file = tmp_path / "installed_exts" / "test-formatter" / "fmt.py"
    assert installed_file.exists()
    assert "def format_code" in installed_file.read_text(encoding="utf-8")

    # List packages
    all_packages = installer.list_installed_packages()
    assert len(all_packages) == 1


def test_install_corrupt_bundle_rejected(installer, sample_bundle, tmp_path):
    dest = str(tmp_path / "installed_exts")
    # Tamper with file content without updating checksum
    tampered_bundle = PackageBundle(
        package_type=sample_bundle.package_type,
        package_id=sample_bundle.package_id,
        version=sample_bundle.version,
        manifest_data=sample_bundle.manifest_data,
        files={"fmt.py": "TAMPERED MALICIOUS CODE"},
        sha256_checksum=sample_bundle.sha256_checksum,  # original checksum
    )

    with pytest.raises(ValueError, match="Package checksum mismatch"):
        installer.install_package(tampered_bundle, dest)


def test_uninstall_package(installer, sample_bundle, tmp_path):
    dest = str(tmp_path / "installed_exts")
    installer.install_package(sample_bundle, dest)
    assert installer.get_installed_package("test-formatter") is not None

    uninstalled = installer.uninstall_package("test-formatter")
    assert uninstalled is True
    assert installer.get_installed_package("test-formatter") is None
