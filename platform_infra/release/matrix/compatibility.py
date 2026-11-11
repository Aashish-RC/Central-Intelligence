"""Component Version Compatibility Matrix (L17 Release - Features 17.02, 17.03).

Tracks semantic version compatibility rules across cognitive and platform layers,
answering pairwise compatibility checks and blocking upgrades that violate constraints.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class UpgradeBlockedError(RuntimeError):
    """Raised when a proposed component upgrade breaks registered compatibility rules."""


def _parse_semver(ver: str) -> Tuple[int, int, int]:
    """Parse 'v2.3.1' or '2.3' into (major, minor, patch)."""
    cleaned = ver.strip().lstrip("vV")
    parts = re.split(r"[.\-+]", cleaned)
    nums: List[int] = []
    for p in parts[:3]:
        m = re.match(r"^(\d+)", p)
        nums.append(int(m.group(1)) if m else 0)
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def satisfies_constraint(version: str, constraint: str) -> bool:
    """Evaluate comma-separated semver bounds such as '>=1.8,<2.0'."""
    ver_t = _parse_semver(version)
    clauses = [c.strip() for c in constraint.split(",") if c.strip()]
    for clause in clauses:
        for op in (">=", "<=", "==", "!=", ">", "<"):
            if clause.startswith(op):
                target_t = _parse_semver(clause[len(op):])
                if op == ">=" and not (ver_t >= target_t):
                    return False
                if op == "<=" and not (ver_t <= target_t):
                    return False
                if op == "==" and not (ver_t == target_t):
                    return False
                if op == "!=" and not (ver_t != target_t):
                    return False
                if op == ">" and not (ver_t > target_t):
                    return False
                if op == "<" and not (ver_t < target_t):
                    return False
                break
        else:
            if ver_t != _parse_semver(clause):
                return False
    return True


@dataclass
class CompatibilityRule:
    """Declares dependency constraint when source component matches source_constraint."""

    source_component: str
    source_constraint: str
    target_component: str
    target_constraint: str
    note: str = ""


@dataclass
class CompatibilityCheckResult:
    """Outcome of a pairwise compatibility check or upgrade validation."""

    compatible: bool
    conflicts: List[str] = field(default_factory=list)
    checked_rules: int = 0


class CompatibilityMatrix:
    """Central compatibility matrix enforcing cross-layer version constraints."""

    def __init__(self) -> None:
        self._rules: List[CompatibilityRule] = []

    def add_rule(self, rule: CompatibilityRule) -> None:
        self._rules.append(rule)

    def check_pair(
        self,
        comp_a: str,
        ver_a: str,
        comp_b: str,
        ver_b: str,
    ) -> CompatibilityCheckResult:
        """Check whether (comp_a@ver_a) and (comp_b@ver_b) satisfy all rules."""
        conflicts: List[str] = []
        checked = 0
        for rule in self._rules:
            if (
                rule.source_component == comp_a
                and rule.target_component == comp_b
                and satisfies_constraint(ver_a, rule.source_constraint)
            ):
                checked += 1
                if not satisfies_constraint(ver_b, rule.target_constraint):
                    conflicts.append(
                        f"{comp_a}@{ver_a} requires {comp_b} {rule.target_constraint}, got {ver_b}"
                    )
            elif (
                rule.source_component == comp_b
                and rule.target_component == comp_a
                and satisfies_constraint(ver_b, rule.source_constraint)
            ):
                checked += 1
                if not satisfies_constraint(ver_a, rule.target_constraint):
                    conflicts.append(
                        f"{comp_b}@{ver_b} requires {comp_a} {rule.target_constraint}, got {ver_a}"
                    )
        return CompatibilityCheckResult(
            compatible=len(conflicts) == 0,
            conflicts=conflicts,
            checked_rules=checked,
        )

    def validate_upgrade(
        self,
        component: str,
        target_version: str,
        current_manifest: Dict[str, str],
        raise_on_conflict: bool = False,
    ) -> CompatibilityCheckResult:
        """Check whether upgrading `component` to `target_version` breaks existing components."""
        conflicts: List[str] = []
        checked = 0
        proposed = dict(current_manifest)
        proposed[component] = target_version

        for other, other_ver in proposed.items():
            if other == component:
                continue
            res = self.check_pair(component, target_version, other, other_ver)
            checked += res.checked_rules
            conflicts.extend(res.conflicts)

        if conflicts and raise_on_conflict:
            raise UpgradeBlockedError("; ".join(conflicts))

        return CompatibilityCheckResult(
            compatible=len(conflicts) == 0,
            conflicts=conflicts,
            checked_rules=checked,
        )

