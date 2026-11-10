"""
Content Rights & Source Attribution Enforcement (Features 10.56, 10.57).
"""

from control.safety.rights.content_rights import (
    AttributionRecord,
    ContentRightsEnforcer,
    ContentRightsResult,
    InfringementMatch,
    ProtectedMaterial,
    default_content_rights_enforcer,
)

__all__ = [
    "AttributionRecord",
    "ContentRightsEnforcer",
    "ContentRightsResult",
    "InfringementMatch",
    "ProtectedMaterial",
    "default_content_rights_enforcer",
]
