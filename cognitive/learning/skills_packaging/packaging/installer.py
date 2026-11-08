"""Installer: Verifies cryptographic integrity, unpacks extensions, and registers active packages."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from ..core.interfaces import BaseInstaller
from ..core.models import (
    InstallationRecord,
    PackageBundle,
)


class Installer(BaseInstaller):
    """Safely verifies package signatures, unpacks files to isolated target directories, and tracks state."""

    def __init__(self):
        # In-memory registry: package_id -> InstallationRecord
        self._installed: Dict[str, InstallationRecord] = {}

    def install_package(
        self, bundle: PackageBundle, destination_root: str
    ) -> InstallationRecord:
        # 1. Cryptographic Checksum Verification
        recalculated = PackageBundle.create(
            package_type=bundle.package_type,
            package_id=bundle.package_id,
            version=bundle.version,
            manifest_data=bundle.manifest_data,
            files=bundle.files,
        )
        if recalculated.sha256_checksum != bundle.sha256_checksum:
            raise ValueError(
                f"Package checksum mismatch! Expected {bundle.sha256_checksum}, computed {recalculated.sha256_checksum}. "
                "Package may be corrupt or tampered."
            )

        # 2. Unpack files into destination
        dest_path = Path(destination_root) / bundle.package_id
        dest_path.mkdir(parents=True, exist_ok=True)

        for rel_path, content in bundle.files.items():
            file_path = dest_path / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        # Write manifest.json
        manifest_file = dest_path / "manifest.json"
        manifest_file.write_text(
            json.dumps(bundle.manifest_data, indent=2), encoding="utf-8"
        )

        record = InstallationRecord(
            package_id=bundle.package_id,
            package_type=bundle.package_type,
            version=bundle.version,
            install_dir=str(dest_path),
            is_active=True,
            checksum=bundle.sha256_checksum,
        )
        self._installed[bundle.package_id] = record
        return record

    def uninstall_package(self, package_id: str) -> bool:
        record = self._installed.pop(package_id, None)
        if not record:
            return False
        dest_path = Path(record.install_dir)
        if dest_path.exists():
            import shutil
            shutil.rmtree(dest_path, ignore_errors=True)
        return True

    def get_installed_package(self, package_id: str) -> Optional[InstallationRecord]:
        return self._installed.get(package_id)

    def list_installed_packages(self) -> List[InstallationRecord]:
        return list(self._installed.values())
