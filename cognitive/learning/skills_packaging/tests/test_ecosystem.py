"""Unit tests for Phase 4 Ecosystem: DependencySolver, MarketplaceCatalog, and LicenseService."""

from datetime import timedelta
import pytest
from skills_packaging.core.models import PackageBundle, PackageType
from skills_packaging.marketplace.catalog import (
    MarketplaceCatalog,
    MarketplaceCategory,
    MarketplaceItem,
)
from skills_packaging.marketplace.license import (
    EntitlementTier,
    LicenseService,
    utc_now,
)
from skills_packaging.packaging.dependency_solver import DependencySolver, VersionConstraint


def test_version_constraint():
    vc_gte = VersionConstraint(">=1.2.0")
    assert vc_gte.satisfies("1.2.0") is True
    assert vc_gte.satisfies("1.3.1") is True
    assert vc_gte.satisfies("1.1.9") is False

    vc_eq = VersionConstraint("==2.0.0")
    assert vc_eq.satisfies("2.0.0") is True
    assert vc_eq.satisfies("2.0.1") is False


def test_dependency_solver_success():
    packages = {
        "pkg_core": {},
        "pkg_auth": {"pkg_core": ">=1.0.0"},
        "pkg_app": {"pkg_auth": ">=1.0.0", "pkg_core": ">=1.0.0"},
    }
    available = {
        "pkg_core": "1.2.0",
        "pkg_auth": "1.0.1",
        "pkg_app": "2.0.0",
    }
    order = DependencySolver.resolve_install_order(packages, available)
    assert order.index("pkg_core") < order.index("pkg_auth")
    assert order.index("pkg_auth") < order.index("pkg_app")


def test_dependency_solver_cycle_detection():
    packages = {
        "pkg_a": {"pkg_b": ">=1.0.0"},
        "pkg_b": {"pkg_a": ">=1.0.0"},
    }
    available = {
        "pkg_a": "1.0.0",
        "pkg_b": "1.0.0",
    }
    with pytest.raises(ValueError, match="Circular dependency detected"):
        DependencySolver.resolve_install_order(packages, available)


def test_marketplace_catalog():
    catalog = MarketplaceCatalog()
    item = MarketplaceItem(
        item_id="ext_code_helper",
        name="Code Helper Pro",
        package_type=PackageType.PLUGIN,
        category=MarketplaceCategory.CODING,
        version="1.0.0",
        description="Assists with code refactoring",
        tags=["python", "refactor"],
        required_tier="free",
    )
    bundle = PackageBundle.create(
        package_type=PackageType.PLUGIN,
        package_id="ext_code_helper",
        version="1.0.0",
        manifest_data={"name": "Code Helper Pro"},
        files={"helper.py": "# Code helper"},
    )
    catalog.publish_item(item, bundle)

    # Search
    results = catalog.search(query="refactor", category=MarketplaceCategory.CODING)
    assert len(results) == 1
    assert results[0].item_id == "ext_code_helper"

    # Download bundle
    downloaded = catalog.get_bundle("ext_code_helper")
    assert downloaded is not None
    assert downloaded.sha256_checksum == bundle.sha256_checksum
    assert catalog.get_item("ext_code_helper").downloads == 1


def test_license_service_tamper_evidence():
    service = LicenseService(secret_key="unit_test_secret_key")
    lic = service.generate_license(
        user_id="user_developer",
        tier=EntitlementTier.PRO,
        features=["advanced_tools", "browser_automation"],
    )

    # Verify valid license
    assert service.verify_license(lic) is True
    assert service.check_entitlement(lic, "free") is True
    assert service.check_entitlement(lic, "pro", feature="advanced_tools") is True
    assert service.check_entitlement(lic, "enterprise") is False

    # Tamper with tier
    lic.tier = EntitlementTier.ENTERPRISE
    assert service.verify_license(lic) is False


def test_license_expiration():
    service = LicenseService(secret_key="unit_test_secret_key")
    past = utc_now() - timedelta(days=1)
    expired_lic = service.generate_license(
        user_id="user_expired",
        tier=EntitlementTier.PRO,
        expires_at=past,
    )
    assert service.verify_license(expired_lic) is False


def test_catalog_request_review_workflow(tmp_path):
    from skills_packaging.marketplace.catalog_requests import CatalogRequestManager, RequestStatus

    catalog = MarketplaceCatalog()
    manager = CatalogRequestManager(catalog=catalog)

    # 1. Clean valid bundle submission
    clean_item = MarketplaceItem(
        item_id="pkg_clean",
        name="Clean Skill",
        package_type=PackageType.SKILL,
        category=MarketplaceCategory.UTILITIES,
        version="1.0.0",
        description="Safe utilities",
    )
    clean_bundle = PackageBundle.create(
        package_type=PackageType.SKILL,
        package_id="pkg_clean",
        version="1.0.0",
        manifest_data={"name": "Clean Skill"},
        files={"main.py": "def run(): return 'safe'"},
    )

    sub = manager.submit_extension(
        tenant_id="tenant_alpha",
        author_id="dev_bob",
        item=clean_item,
        bundle=clean_bundle,
    )
    assert sub.status == RequestStatus.IN_REVIEW
    assert sub.security_scan_passed is True

    # Review & approve
    approved = manager.review_submission(
        submission_id=sub.submission_id,
        approved=True,
        reviewer_id="admin_alice",
        notes="Code reviewed and verified safe.",
    )
    assert approved.status == RequestStatus.PUBLISHED
    assert catalog.get_item("pkg_clean") is not None

    # 2. Dangerous bundle submission (with eval)
    bad_item = MarketplaceItem(
        item_id="pkg_bad",
        name="Bad Skill",
        package_type=PackageType.SKILL,
        category=MarketplaceCategory.UTILITIES,
        version="1.0.0",
        description="Suspicious code",
    )
    bad_bundle = PackageBundle.create(
        package_type=PackageType.SKILL,
        package_id="pkg_bad",
        version="1.0.0",
        manifest_data={"name": "Bad Skill"},
        files={"bad.py": "result = eval(user_input)"},
    )

    bad_sub = manager.submit_extension(
        tenant_id="tenant_alpha",
        author_id="dev_mal",
        item=bad_item,
        bundle=bad_bundle,
    )
    assert bad_sub.status == RequestStatus.REJECTED
    assert bad_sub.security_scan_passed is False
    assert any("eval()" in msg for msg in bad_sub.security_scan_report)


def test_update_manager_staging_preview(tmp_path):
    from skills_packaging.marketplace.update_manager import UpdateManager
    from skills_packaging.packaging.installer import Installer

    catalog = MarketplaceCatalog()
    installer = Installer()
    update_mgr = UpdateManager(catalog=catalog)

    # Initial v1.0.0 bundle
    v1_bundle = PackageBundle.create(
        package_type=PackageType.PLUGIN,
        package_id="pkg_calculator",
        version="1.0.0",
        manifest_data={"name": "Calculator", "version": "1.0.0"},
        files={"calc.py": "def add(a, b): return a + b\n", "old.py": "# Deprecated\n"},
    )
    installer.install_package(v1_bundle, str(tmp_path / "installed"))

    # Publish v2.0.0 bundle to catalog
    v2_item = MarketplaceItem(
        item_id="pkg_calculator",
        name="Calculator",
        package_type=PackageType.PLUGIN,
        category=MarketplaceCategory.UTILITIES,
        version="2.0.0",
        description="Major upgrade with multiply",
    )
    v2_bundle = PackageBundle.create(
        package_type=PackageType.PLUGIN,
        package_id="pkg_calculator",
        version="2.0.0",
        manifest_data={"name": "Calculator", "version": "2.0.0"},
        files={
            "calc.py": "def add(a, b): return a + b\ndef multiply(a, b): return a * b\n",
            "new_feature.py": "# New module\n",
        },
    )
    catalog.publish_item(v2_item, v2_bundle)

    # Check available updates
    updates = update_mgr.check_updates(installer)
    assert len(updates) == 1
    assert updates[0]["package_id"] == "pkg_calculator"
    assert updates[0]["latest_version"] == "2.0.0"

    # Generate non-destructive dry-run staging preview
    preview = update_mgr.create_staging_preview("pkg_calculator", installer)
    assert preview.package_id == "pkg_calculator"
    assert preview.current_version == "1.0.0"
    assert preview.target_version == "2.0.0"
    assert "new_feature.py" in preview.files_added
    assert "calc.py" in preview.files_modified
    assert "old.py" in preview.files_removed
    assert preview.breaking_change_warning is True  # Major version bump 1.0 -> 2.0

    # Apply staged update with rollback backup
    backup_dir = str(tmp_path / "backups")
    new_rec = update_mgr.apply_staged_update("pkg_calculator", installer, backup_dir=backup_dir)
    assert new_rec.version == "2.0.0"

    # Rollback update
    rolled_back = update_mgr.rollback_update("pkg_calculator", installer)
    assert rolled_back is True
    # Confirm old file restored
    assert (tmp_path / "installed" / "pkg_calculator" / "old.py").exists()

