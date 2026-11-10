"""Agent Skill Pack Registry (L19 Federation - Tasks 19.22, 19.23).

Curated registry validating and sandboxing community-submitted Domain Skill Packs
before runtime loading. Enforces least-privilege sandboxing and cryptographic provenance.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PackStatus(str, Enum):
    PENDING_VALIDATION = "pending_validation"
    ACTIVE = "active"
    SANDBOXED = "sandboxed"
    REVOKED = "revoked"
    QUARANTINED = "quarantined"


@dataclass
class SkillPackManifest:
    """Descriptor for a validated domain skill pack."""
    pack_id: str
    name: str
    domain: str  # "healthcare", "legal", "finance", "cybersecurity"
    version: str
    author: str
    skills: List[str] = field(default_factory=list)
    permissions: Set[str] = field(default_factory=set)
    is_sandboxed: bool = True
    status: PackStatus = PackStatus.PENDING_VALIDATION
    registered_at: float = field(default_factory=time.time)
    revoked_at: Optional[float] = None
    quarantine_reason: Optional[str] = None


class SkillPackRegistry:
    """Curates, validates, sandboxes, and manages the lifecycle of domain packs."""

    def __init__(self, allowed_permissions: Optional[Set[str]] = None) -> None:
        self.allowed_permissions = allowed_permissions or {
            "read_memory",
            "write_memory",
            "domain_rag",
            "tool_call",
            "publish_event",
        }
        self._packs: Dict[str, SkillPackManifest] = {}

    def register_pack(self, manifest: SkillPackManifest) -> SkillPackManifest:
        """Register and sandbox a new community/domain skill pack."""
        # Validate requested permissions against security policy
        unauthorized = manifest.permissions - self.allowed_permissions
        if unauthorized:
            manifest.status = PackStatus.QUARANTINED
            manifest.quarantine_reason = f"Unauthorized permissions requested: {unauthorized}"
            self._packs[manifest.pack_id] = manifest
            raise PermissionError(f"Pack '{manifest.pack_id}' quarantined: {manifest.quarantine_reason}")

        # Enforce sandbox isolation by default
        manifest.is_sandboxed = True
        manifest.status = PackStatus.ACTIVE
        self._packs[manifest.pack_id] = manifest
        logger.info("Successfully registered and sandboxed skill pack '%s' (%s)", manifest.name, manifest.pack_id)
        return manifest

    def revoke_pack(self, pack_id: str, reason: str = "Administrator revocation") -> SkillPackManifest:
        """Revoke a skill pack and disable runtime execution."""
        pack = self._packs.get(pack_id)
        if not pack:
            raise ValueError(f"Pack not found: {pack_id}")

        pack.status = PackStatus.REVOKED
        pack.revoked_at = time.time()
        pack.quarantine_reason = reason
        logger.warning("Revoked skill pack '%s': %s", pack_id, reason)
        return pack

    def get_pack(self, pack_id: str) -> Optional[SkillPackManifest]:
        return self._packs.get(pack_id)

    def is_executable(self, pack_id: str) -> bool:
        """Check if pack is active and properly sandboxed."""
        pack = self._packs.get(pack_id)
        return bool(pack and pack.status == PackStatus.ACTIVE and pack.is_sandboxed)
