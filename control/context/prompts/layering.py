"""Instruction Layering & Precedence Rules (Layer 9, Features 9.07, 9.10)."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional


class InstructionTier(IntEnum):
    """Hierarchical instruction layers ordered by evaluation priority (higher overrides lower)."""
    GLOBAL = 1
    TENANT = 2
    APP = 3
    USER = 4


@dataclass
class LayeredDirective:
    """A specific instruction directive bound to a layer and scope."""
    key: str
    content: str
    tier: InstructionTier
    scope_id: Optional[str] = None  # tenant_id, app_id, or user_id
    immutable: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class InstructionLayerResolver:
    """Resolves hierarchical instruction layers with deterministic precedence (9.07, 9.10).

    Precedence cascade:
    User-level > App-level > Tenant-level > Global-level.
    An immutable lower-tier directive (e.g. system safety baseline in Global) CANNOT be
    overridden by a higher-tier directive unless explicitly permitted.
    """

    @staticmethod
    def resolve(
        global_directives: List[LayeredDirective],
        tenant_directives: Optional[List[LayeredDirective]] = None,
        app_directives: Optional[List[LayeredDirective]] = None,
        user_directives: Optional[List[LayeredDirective]] = None,
    ) -> List[LayeredDirective]:
        tenant_directives = tenant_directives or []
        app_directives = app_directives or []
        user_directives = user_directives or []

        # Map key to active directive and provenance
        resolved_map: Dict[str, LayeredDirective] = {}
        immutable_keys: Dict[str, LayeredDirective] = {}

        # 1. Ingest Global (Tier 1)
        for d in global_directives:
            resolved_map[d.key] = d
            if d.immutable:
                immutable_keys[d.key] = d

        # 2. Ingest Tenant (Tier 2) - overrides Global unless Global is immutable
        for d in tenant_directives:
            if d.key in immutable_keys and not d.metadata.get("force_override"):
                continue  # Cannot override immutable global rule
            resolved_map[d.key] = d

        # 3. Ingest App (Tier 3) - overrides Tenant & Global
        for d in app_directives:
            if d.key in immutable_keys and not d.metadata.get("force_override"):
                continue
            resolved_map[d.key] = d

        # 4. Ingest User (Tier 4) - overrides App, Tenant, and Global
        for d in user_directives:
            if d.key in immutable_keys and not d.metadata.get("force_override"):
                continue
            resolved_map[d.key] = d

        return list(resolved_map.values())

    @staticmethod
    def format_resolved_directives(directives: List[LayeredDirective]) -> str:
        """Serializes resolved directives into a structured system instruction block."""
        # Sort by tier ascending for logical reading order
        sorted_directives = sorted(directives, key=lambda d: d.tier.value)
        blocks = []
        for d in sorted_directives:
            tier_name = d.tier.name.lower()
            scope = f" scope=\"{d.scope_id}\"" if d.scope_id else ""
            blocks.append(f"<directive key=\"{d.key}\" tier=\"{tier_name}\"{scope}>\n{d.content.strip()}\n</directive>")
        return "\n\n".join(blocks)
