"""Tests for L17 Compatibility Matrix."""

import pytest

from platform_infra.release.matrix.compatibility import (
    CompatibilityMatrix,
    CompatibilityRule,
    UpgradeBlockedError,
)


def test_l4_l2_compatibility_and_upgrade_blocking():
    matrix = CompatibilityMatrix()
    matrix.add_rule(
        CompatibilityRule(
            source_component="L4",
            source_constraint=">=2.0,<3.0",
            target_component="L2",
            target_constraint=">=1.8,<2.0",
            note="L4 v2.x relies on L2 1.8+ memory schema",
        )
    )

    ok = matrix.check_pair("L4", "2.3", "L2", "1.8")
    assert ok.compatible is True
    assert ok.checked_rules == 1

    bad = matrix.check_pair("L4", "2.3", "L2", "1.5")
    assert bad.compatible is False
    assert "L4@2.3 requires L2 >=1.8,<2.0, got 1.5" in bad.conflicts[0]

    manifest = {"L4": "2.3", "L2": "1.8"}
    blocked = matrix.validate_upgrade("L2", "2.0", manifest)
    assert blocked.compatible is False

    with pytest.raises(UpgradeBlockedError):
        matrix.validate_upgrade("L2", "2.0", manifest, raise_on_conflict=True)

