"""Packager: Bundles skill and plugin source files and manifests into cryptographic packages."""

import re
from typing import Dict
from ..core.interfaces import BasePackager
from ..core.models import (
    PackageBundle,
    PackageType,
    PluginManifest,
    SkillManifest,
)

SEMVER_REGEX = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


class Packager(BasePackager):
    """Constructs verifiable, tamper-evident portable skill and plugin packages."""

    def package_skill(
        self, manifest: SkillManifest, files: Dict[str, str]
    ) -> PackageBundle:
        if not SEMVER_REGEX.match(manifest.version):
            raise ValueError(f"Invalid SemVer format '{manifest.version}' in skill manifest")
        if manifest.entrypoint not in files:
            raise ValueError(
                f"Entrypoint '{manifest.entrypoint}' declared in manifest is missing from file package"
            )

        manifest_data = manifest.model_dump()
        return PackageBundle.create(
            package_type=PackageType.SKILL,
            package_id=manifest.skill_id,
            version=manifest.version,
            manifest_data=manifest_data,
            files=files,
        )

    def package_plugin(
        self, manifest: PluginManifest, files: Dict[str, str]
    ) -> PackageBundle:
        if not SEMVER_REGEX.match(manifest.version):
            raise ValueError(f"Invalid SemVer format '{manifest.version}' in plugin manifest")
        if not manifest.bundled_skills:
            raise ValueError("PluginManifest must bundle at least one skill")

        manifest_data = manifest.model_dump()
        return PackageBundle.create(
            package_type=PackageType.PLUGIN,
            package_id=manifest.plugin_id,
            version=manifest.version,
            manifest_data=manifest_data,
            files=files,
        )
