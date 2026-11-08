"""Update Manager with Staging Previews: Staged rollouts, diff generation, breaking change detection, and rollback safety."""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .catalog import MarketplaceCatalog
from ..core.models import InstallationRecord, PackageBundle
from ..packaging.dependency_solver import VersionConstraint
from ..packaging.installer import Installer


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UpdateStatus(str, Enum):
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    PREVIEW_GENERATED = "preview_generated"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class UpdatePreview(BaseModel):
    package_id: str
    current_version: str
    target_version: str
    files_added: List[str] = Field(default_factory=list)
    files_modified: List[str] = Field(default_factory=list)
    files_removed: List[str] = Field(default_factory=list)
    breaking_change_warning: bool = False
    checksum_valid: bool = True
    summary: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class UpdateManager:
    """Manages dry-run staging previews, version checking, atomic rollout, and rollbacks for extensions."""

    def __init__(self, catalog: MarketplaceCatalog):
        self.catalog = catalog
        self._backups: Dict[str, str] = {}  # package_id -> backup_dir_path

    def check_updates(self, installer: Installer) -> List[Dict[str, Any]]:
        """Compares installed package versions against available catalog versions."""
        available_updates = []
        installed_packages = installer.list_installed_packages()

        for inst in installed_packages:
            cat_item = self.catalog.get_item(inst.package_id)
            if not cat_item:
                continue

            # Compare versions
            c_constraint = VersionConstraint(f">{inst.version}")
            if c_constraint.satisfies(cat_item.version):
                available_updates.append({
                    "package_id": inst.package_id,
                    "current_version": inst.version,
                    "latest_version": cat_item.version,
                    "category": cat_item.category.value,
                    "required_tier": cat_item.required_tier,
                })

        return available_updates

    def create_staging_preview(self, package_id: str, installer: Installer) -> UpdatePreview:
        """Generates a non-destructive dry-run diff preview before applying an update."""
        inst = installer.get_installed_package(package_id)
        if not inst:
            raise ValueError(f"Package '{package_id}' is not currently installed.")

        bundle = self.catalog.get_bundle(package_id)
        if not bundle:
            raise ValueError(f"Package bundle for '{package_id}' not found in catalog.")

        # Inspect current installed files on disk
        install_dir = Path(inst.install_dir)
        existing_files: Dict[str, str] = {}
        if install_dir.exists():
            for f in install_dir.rglob("*"):
                if f.is_file() and f.name != "manifest.json":
                    rel = str(f.relative_to(install_dir)).replace("\\", "/")
                    try:
                        existing_files[rel] = f.read_text(encoding="utf-8")
                    except Exception:
                        existing_files[rel] = ""

        # Compute diffs against new bundle
        added = [f for f in bundle.files if f not in existing_files]
        modified = [f for f in bundle.files if f in existing_files and bundle.files[f] != existing_files[f]]
        removed = [f for f in existing_files if f not in bundle.files]

        # Check for potential breaking changes (e.g., major version bump)
        try:
            curr_major = int(inst.version.split(".")[0])
            target_major = int(bundle.version.split(".")[0])
            is_breaking = target_major > curr_major
        except Exception:
            is_breaking = False

        summary = (
            f"Update from {inst.version} -> {bundle.version}: "
            f"+{len(added)} added, ~{len(modified)} modified, -{len(removed)} removed."
        )

        return UpdatePreview(
            package_id=package_id,
            current_version=inst.version,
            target_version=bundle.version,
            files_added=added,
            files_modified=modified,
            files_removed=removed,
            breaking_change_warning=is_breaking,
            checksum_valid=bool(bundle.sha256_checksum),
            summary=summary,
        )

    def apply_staged_update(
        self,
        package_id: str,
        installer: Installer,
        backup_dir: str = "./backups",
    ) -> InstallationRecord:
        """Applies an update while creating an atomic rollback snapshot."""
        inst = installer.get_installed_package(package_id)
        if not inst:
            raise ValueError(f"Package '{package_id}' is not installed.")

        bundle = self.catalog.get_bundle(package_id)
        if not bundle:
            raise ValueError(f"Package bundle for '{package_id}' not found in catalog.")

        # Create rollback snapshot
        b_path = Path(backup_dir) / f"{package_id}_{inst.version}_{int(datetime.now().timestamp())}"
        b_path.parent.mkdir(parents=True, exist_ok=True)
        if Path(inst.install_dir).exists():
            shutil.copytree(inst.install_dir, b_path, dirs_exist_ok=True)
            self._backups[package_id] = str(b_path)

        # Execute safe installation of target bundle
        dest_root = Path(inst.install_dir).parent
        new_record = installer.install_package(bundle, str(dest_root))
        return new_record

    def rollback_update(self, package_id: str, installer: Installer) -> bool:
        """Restores the package from the last known backup snapshot."""
        backup_path_str = self._backups.get(package_id)
        if not backup_path_str or not Path(backup_path_str).exists():
            return False

        inst = installer.get_installed_package(package_id)
        if not inst:
            return False

        dest_path = Path(inst.install_dir)
        if dest_path.exists():
            shutil.rmtree(dest_path, ignore_errors=True)

        shutil.copytree(backup_path_str, dest_path, dirs_exist_ok=True)
        return True
