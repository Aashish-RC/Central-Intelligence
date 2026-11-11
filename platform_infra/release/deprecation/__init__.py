"""Deprecation policy & sunset management package for L17 Release."""

from platform_infra.release.deprecation.policy import (
    DeprecationNotice,
    DeprecationPolicyManager,
    DeprecationStatus,
    FeatureDeprecatedError,
)

__all__ = [
    "DeprecationNotice",
    "DeprecationPolicyManager",
    "DeprecationStatus",
    "FeatureDeprecatedError",
]

