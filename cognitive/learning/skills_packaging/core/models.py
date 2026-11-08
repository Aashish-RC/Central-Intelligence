"""Core data models for Pheonix Skills and Plugin Packaging."""

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PackageType(str, Enum):
    SKILL = "skill"
    PLUGIN = "plugin"


class SkillManifest(BaseModel):
    skill_id: str
    name: str
    version: str = "0.1.0"
    description: str
    entrypoint: str = "main.py"
    required_tools: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    author: str = "Pheonix Developer"


class PluginManifest(BaseModel):
    plugin_id: str
    name: str
    version: str = "0.1.0"
    description: str
    bundled_skills: List[SkillManifest] = Field(default_factory=list)
    mcp_servers: List[str] = Field(default_factory=list)
    rules: List[str] = Field(default_factory=list)
    hooks: List[str] = Field(default_factory=list)
    author: str = "Pheonix Developer"


class PackageBundle(BaseModel):
    package_type: PackageType
    package_id: str
    version: str
    manifest_data: Dict[str, Any]
    files: Dict[str, str] = Field(default_factory=dict)  # relative_path -> file content
    sha256_checksum: str
    created_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        package_type: PackageType,
        package_id: str,
        version: str,
        manifest_data: Dict[str, Any],
        files: Dict[str, str],
    ) -> "PackageBundle":
        # Calculate deterministic SHA-256 digest
        hasher = hashlib.sha256()
        hasher.update(package_type.value.encode())
        hasher.update(package_id.encode())
        hasher.update(version.encode())
        hasher.update(json.dumps(manifest_data, sort_keys=True).encode())
        for path in sorted(files.keys()):
            hasher.update(path.encode())
            hasher.update(files[path].encode())
        checksum = hasher.hexdigest()

        return cls(
            package_type=package_type,
            package_id=package_id,
            version=version,
            manifest_data=manifest_data,
            files=files,
            sha256_checksum=checksum,
        )


class InstallationRecord(BaseModel):
    package_id: str
    package_type: PackageType
    version: str
    install_dir: str
    installed_at: datetime = Field(default_factory=utc_now)
    is_active: bool = True
    checksum: str


class ExecutionResult(BaseModel):
    package_id: str
    output: str
    status: str = "completed"
    duration_ms: float = 0.0
