"""Dependency Solver: Resolves package dependencies, version constraints, and topological install ordering."""

from typing import Dict, List, Optional, Set
import re


class VersionConstraint:
    """Evaluates semver-like version constraint strings such as '>=0.1.0' or '==1.2.0'."""

    PATTERN = re.compile(r"^(>=|<=|>|<|==)?\s*([0-9]+(?:\.[0-9]+)*)$")

    def __init__(self, spec: str):
        self.spec = spec.strip()
        match = self.PATTERN.match(self.spec)
        if not match:
            # Fallback to exact match or wildcard
            self.op = "=="
            self.target_parts = [0, 1, 0]
        else:
            self.op = match.group(1) or "=="
            self.target_parts = [int(p) for p in match.group(2).split(".")]

    def satisfies(self, version_str: str) -> bool:
        try:
            ver_parts = [int(p) for p in version_str.split(".")]
        except Exception:
            return False

        # Pad to equal length
        max_len = max(len(ver_parts), len(self.target_parts))
        v1 = ver_parts + [0] * (max_len - len(ver_parts))
        v2 = self.target_parts + [0] * (max_len - len(self.target_parts))

        if self.op == "==":
            return v1 == v2
        elif self.op == ">=":
            return v1 >= v2
        elif self.op == "<=":
            return v1 <= v2
        elif self.op == ">":
            return v1 > v2
        elif self.op == "<":
            return v1 < v2
        return False


class DependencySolver:
    """Solves installation order and validates dependency graph without circular references."""

    @classmethod
    def resolve_install_order(
        cls,
        packages: Dict[str, Dict[str, str]],  # package_id -> {dep_id: version_constraint}
        available_versions: Dict[str, str],   # package_id -> available_version
    ) -> List[str]:
        """Returns topological list of package IDs to install in order.
        Raises ValueError if circular dependency or unsatisfied requirement is found.
        """
        # Validate all dependencies can be satisfied
        for pkg_id, deps in packages.items():
            for dep_id, constraint_str in deps.items():
                if dep_id not in available_versions:
                    raise ValueError(f"Package '{pkg_id}' requires missing dependency '{dep_id}'")
                actual_ver = available_versions[dep_id]
                constraint = VersionConstraint(constraint_str)
                if not constraint.satisfies(actual_ver):
                    raise ValueError(
                        f"Unsatisfied dependency for '{pkg_id}': '{dep_id}' version '{actual_ver}' "
                        f"does not satisfy constraint '{constraint_str}'"
                    )

        # Topological sort (Kahn's algorithm)
        in_degree: Dict[str, int] = {pkg: 0 for pkg in packages}
        dependents: Dict[str, List[str]] = {pkg: [] for pkg in packages}

        for pkg, deps in packages.items():
            for dep in deps:
                if dep in packages:
                    in_degree[pkg] += 1
                    dependents[dep].append(pkg)

        queue = [pkg for pkg, deg in in_degree.items() if deg == 0]
        order: List[str] = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for dep_of_node in dependents.get(node, []):
                in_degree[dep_of_node] -= 1
                if in_degree[dep_of_node] == 0:
                    queue.append(dep_of_node)

        if len(order) < len(packages):
            cycle_nodes = [pkg for pkg, deg in in_degree.items() if deg > 0]
            raise ValueError(f"Circular dependency detected among packages: {cycle_nodes}")

        return order
