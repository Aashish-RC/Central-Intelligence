"""Repository license, Docker image pinning, secret hygiene, and lockfile check."""

from __future__ import annotations

import importlib.metadata
import os
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    import tomli as tomllib  # type: ignore[no-redef]


REPO_ROOT = Path(__file__).resolve().parent.parent

# Audited Docker Compose services mapped to (license_spdx, osi_approved).
REVIEWED_COMPOSE_SERVICES: dict[str, tuple[str, bool]] = {
    "qdrant": ("Apache-2.0", True),
    "ollama": ("MIT", True),
    "meilisearch": ("MIT", True),
    "valkey": ("BSD-3-Clause", True),
    "chroma": ("Apache-2.0", True),
    "memgraph": ("BSL-1.1", False),
    "falkordb": ("SSPL-v1", False),
    "nango": ("Elastic-2.0", False),
    "temporal": ("MIT", True),
    "otel-collector": ("Apache-2.0", True),
    "phoenix": ("Elastic-2.0", False),
    "keycloak": ("Apache-2.0", True),
    "openfga": ("Apache-2.0", True),
    "infisical": ("MIT", True),
    "hyperswitch": ("Apache-2.0", True),
    "livekit": ("Apache-2.0", True),
    "supabase-db": ("Apache-2.0 / PostgreSQL", True),
    "apache-age": ("Apache-2.0", True),
    "huly": ("EPL-2.0", True),
}

# Packages that include dual licensing or permissive runtime exceptions alongside GPL.
PERMISSIVE_DUAL_LICENSE_HINTS = ("apache", "mit", "bsd", "psf", "isc", "mpl")

# Regex matching ${VAR:-default} or ${VAR-default} for credential-like env vars.
SECRET_FALLBACK_RE = re.compile(
    r"\$\{([A-Z0-9_]*(?:_KEY|_KEYS|SECRET|PASSWORD|TOKEN|CREDENTIAL)[A-Z0-9_]*):?-[^}]+\}"
)


# Packages that must never be pinned in core requirements.lock:
# - litellm: supply-chain exclusion
# - tensorflow / keras / tensorboard / gqlalchemy / falkordb: heavy or non-OSI graph extras
# - lago / lago-python-client: AGPL-3.0 boundary (REST HTTP/JSON only)
DISALLOWED_LOCK_PACKAGES = (
    "litellm",
    "tensorflow",
    "keras",
    "tensorboard",
    "gqlalchemy",
    "falkordb",
    "lago",
    "lago-python-client",
)

LAGO_IMPORT_RE = re.compile(r"(?m)^\s*(?:from|import)\s+lago(?:_python_client)?\b")
VENV_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__"}


def check_repo_license_files() -> list[str]:
    """Verify LICENSE, NOTICE, .env.example, requirements.lock, Lago boundary, and pyproject metadata."""
    errors: list[str] = []
    license_path = REPO_ROOT / "LICENSE"
    if not license_path.is_file():
        errors.append("Missing root LICENSE file.")
    elif "Apache License" not in license_path.read_text(encoding="utf-8"):
        errors.append("Root LICENSE does not contain Apache License text.")

    for req_rel in ("NOTICE", "control/orchestration/nodes/NOTICE", ".env.example"):
        if not (REPO_ROOT / req_rel).is_file():
            errors.append(f"Missing required governance file: {req_rel}")

    lock_path = REPO_ROOT / "requirements.lock"
    if not lock_path.is_file():
        errors.append("Missing pinned hashed lockfile: requirements.lock")
    else:
        lock_text = lock_path.read_text(encoding="utf-8")
        if "--hash=sha256:" not in lock_text:
            errors.append("requirements.lock must include --hash=sha256: entries.")
        for pkg in DISALLOWED_LOCK_PACKAGES:
            if re.search(rf"(?mi)^{re.escape(pkg)}==", lock_text):
                errors.append(f"requirements.lock must not pin disallowed/optional package '{pkg}'.")

    for root, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in VENV_SKIP_DIRS]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            py_file = Path(root) / filename
            rel = py_file.relative_to(REPO_ROOT).as_posix()
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            if LAGO_IMPORT_RE.search(text):
                errors.append(
                    f"AGPL boundary violation in {rel}: direct import of Lago Python package is forbidden (use REST HTTP/JSON only)."
                )

    pyproject_data = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    license_meta = pyproject_data.get("project", {}).get("license", {})
    declared = (
        license_meta.get("text")
        if isinstance(license_meta, dict)
        else str(license_meta)
    )
    if declared != "Apache-2.0":
        errors.append(
            f"pyproject.toml project.license must be 'Apache-2.0', got {declared!r}."
        )
    return errors


def _parse_compose_services(compose_text: str) -> dict[str, dict[str, str]]:
    """Extract top-level compose service metadata without external YAML parser."""
    services: dict[str, dict[str, str]] = {}
    current_service: str | None = None
    in_services = False

    for raw_line in compose_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent == 0:
            in_services = stripped == "services:"
            current_service = None
            continue
        if not in_services:
            continue
        if indent == 2 and stripped.endswith(":"):
            current_service = stripped[:-1].strip()
            services[current_service] = {}
        elif indent == 4 and current_service:
            if stripped.startswith("image:"):
                services[current_service]["image"] = (
                    stripped.split("image:", 1)[1].strip().strip("'\"")
                )
            elif stripped.startswith("profiles:"):
                services[current_service]["profiles"] = (
                    stripped.split("profiles:", 1)[1].strip()
                )
    return services


def check_docker_compose() -> tuple[list[str], list[str]]:
    """Validate pinned image tags, secret hygiene, and OSI-default profile gating."""
    errors: list[str] = []
    warnings: list[str] = []
    compose_path = REPO_ROOT / "docker-compose.yml"
    compose_text = compose_path.read_text(encoding="utf-8")

    services = _parse_compose_services(compose_text)
    if not services:
        errors.append("No services/images found in docker-compose.yml.")
        return errors, warnings

    for service, meta in services.items():
        image = meta.get("image", "")
        if ":" not in image or image.endswith(":latest"):
            errors.append(
                f"Compose service '{service}' uses unpinned/latest image '{image}'."
            )
        review = REVIEWED_COMPOSE_SERVICES.get(service)
        if review is None:
            errors.append(
                f"Compose service '{service}' ({image}) is not documented in docs/LICENSE_AUDIT.md / check_licenses.py."
            )
        elif not review[1]:
            if not meta.get("profiles"):
                errors.append(
                    f"Non-OSI service '{service}' ({review[0]}) must specify a compose profile so it is excluded from the default stack."
                )
            else:
                warnings.append(
                    f"Opt-in non-OSI compose service '{service}' ({image}, {review[0]}, profile={meta['profiles']})"
                )

    for match in SECRET_FALLBACK_RE.finditer(compose_text):
        errors.append(
            f"Committed default secret fallback found for '{match.group(1)}' in docker-compose.yml."
        )

    return errors, warnings


def _extract_package_license(dist: importlib.metadata.Distribution) -> str:
    """Return normalized license metadata string for a Python distribution."""
    meta = dist.metadata
    expr = meta.get("License-Expression")
    if expr:
        return expr.strip()
    lic = meta.get("License")
    if lic and lic.strip() and lic.strip().upper() != "UNKNOWN":
        return lic.strip().splitlines()[0]
    classifiers = [
        c.split("::")[-1].strip()
        for c in (meta.get_all("Classifier") or [])
        if c.startswith("License ::")
    ]
    return "; ".join(classifiers) if classifiers else "UNKNOWN"


def check_python_dependencies() -> tuple[list[str], list[str]]:
    """Flag installed Python dependencies with strong-copyleft licenses without dual option."""
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()

    for dist in importlib.metadata.distributions():
        name = (dist.metadata.get("Name") or "unknown").lower()
        if name in seen:
            continue
        seen.add(name)
        lic_text = _extract_package_license(dist)
        lower = lic_text.lower()
        if "agpl" in lower or ("gpl" in lower and "lgpl" not in lower):
            has_permissive = any(hint in lower for hint in PERMISSIVE_DUAL_LICENSE_HINTS)
            if not has_permissive:
                errors.append(
                    f"Strong-copyleft Python package detected: {name} ({lic_text})"
                )
            else:
                warnings.append(
                    f"Dual-licensed Python package ({lic_text}): {name}"
                )

    return errors, warnings


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(check_repo_license_files())
    compose_errors, compose_warnings = check_docker_compose()
    errors.extend(compose_errors)
    warnings.extend(compose_warnings)

    dep_errors, dep_warnings = check_python_dependencies()
    errors.extend(dep_errors)
    warnings.extend(dep_warnings)

    for warning in warnings:
        print(f"WARN: {warning}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        "License, lockfile hash, Docker tag pinning, and secret hygiene checks passed "
        f"({len(REVIEWED_COMPOSE_SERVICES)} compose services verified)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
