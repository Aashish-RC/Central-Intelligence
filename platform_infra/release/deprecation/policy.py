"""Deprecation Policy, Sunset Dates & Migration Guides (L17 Release - Feature 17.08).

Registers formal deprecation notices, tracks sunset dates, generates standard
Deprecation/Sunset HTTP headers, and enforces post-sunset removal rules.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class DeprecationStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    PAST_SUNSET = "past_sunset"


class FeatureDeprecatedError(RuntimeError):
    """Raised when a feature past its sunset date is invoked under strict enforcement."""


@dataclass
class DeprecationNotice:
    """Formal deprecation record for an API, model, or platform capability."""

    feature_id: str
    deprecated_since: datetime.date
    sunset_date: datetime.date
    replacement: str
    migration_guide_url: str
    message: str = ""


class DeprecationPolicyManager:
    """Manages deprecation lifecycle, HTTP headers, and sunset enforcement."""

    def __init__(self) -> None:
        self._notices: Dict[str, DeprecationNotice] = {}

    def deprecate(
        self,
        feature_id: str,
        sunset_date: datetime.date,
        replacement: str,
        migration_guide_url: str,
        deprecated_since: Optional[datetime.date] = None,
        message: str = "",
    ) -> DeprecationNotice:
        """Mark a feature as deprecated with a target sunset date and migration guide."""
        since = deprecated_since or datetime.date.today()
        if sunset_date < since:
            raise ValueError("sunset_date cannot precede deprecated_since")
        notice = DeprecationNotice(
            feature_id=feature_id,
            deprecated_since=since,
            sunset_date=sunset_date,
            replacement=replacement,
            migration_guide_url=migration_guide_url,
            message=message or f"Use '{replacement}' instead.",
        )
        self._notices[feature_id] = notice
        return notice

    def get_status(
        self,
        feature_id: str,
        as_of: Optional[datetime.date] = None,
    ) -> DeprecationStatus:
        """Determine lifecycle status for a feature at date `as_of`."""
        notice = self._notices.get(feature_id)
        if not notice:
            return DeprecationStatus.ACTIVE
        ref = as_of or datetime.date.today()
        if ref >= notice.sunset_date:
            return DeprecationStatus.PAST_SUNSET
        return DeprecationStatus.DEPRECATED

    def build_headers(self, feature_id: str) -> Dict[str, str]:
        """Generate RFC-style Deprecation, Sunset, and Link headers for responses."""
        notice = self._notices.get(feature_id)
        if not notice:
            return {}
        return {
            "Deprecation": f"@{int(datetime.datetime.combine(notice.deprecated_since, datetime.time.min, tzinfo=datetime.timezone.utc).timestamp())}",
            "Sunset": notice.sunset_date.isoformat(),
            "Link": f'<{notice.migration_guide_url}>; rel="deprecation"',
            "X-Replacement-Feature": notice.replacement,
        }

    def check_allowed(
        self,
        feature_id: str,
        as_of: Optional[datetime.date] = None,
        strict: bool = True,
    ) -> DeprecationStatus:
        """Check usage permission; raises FeatureDeprecatedError after sunset if strict=True."""
        status = self.get_status(feature_id, as_of=as_of)
        if strict and status == DeprecationStatus.PAST_SUNSET:
            notice = self._notices[feature_id]
            raise FeatureDeprecatedError(
                f"Feature '{feature_id}' passed sunset date {notice.sunset_date.isoformat()}. "
                f"Migrate to '{notice.replacement}' ({notice.migration_guide_url})."
            )
        return status

    def list_deprecations(self) -> List[DeprecationNotice]:
        return list(self._notices.values())

