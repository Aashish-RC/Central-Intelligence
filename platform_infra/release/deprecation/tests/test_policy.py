"""Tests for L17 Deprecation Policy Manager."""

import datetime

import pytest

from platform_infra.release.deprecation.policy import (
    DeprecationPolicyManager,
    DeprecationStatus,
    FeatureDeprecatedError,
)


def test_mark_deprecated_with_sunset_and_enforce():
    mgr = DeprecationPolicyManager()
    notice = mgr.deprecate(
        feature_id="v1.chat.completions",
        deprecated_since=datetime.date(2026, 11, 1),
        sunset_date=datetime.date(2027, 2, 1),
        replacement="v2.responses",
        migration_guide_url="https://docs.local/migrate-v2",
    )
    assert notice.feature_id == "v1.chat.completions"
    assert mgr.get_status("v1.chat.completions", as_of=datetime.date(2026, 11, 15)) == DeprecationStatus.DEPRECATED

    headers = mgr.build_headers("v1.chat.completions")
    assert headers["Sunset"] == "2027-02-01"
    assert "migrate-v2" in headers["Link"]

    assert mgr.check_allowed("v1.chat.completions", as_of=datetime.date(2026, 12, 1)) == DeprecationStatus.DEPRECATED
    with pytest.raises(FeatureDeprecatedError):
        mgr.check_allowed("v1.chat.completions", as_of=datetime.date(2027, 2, 1), strict=True)

