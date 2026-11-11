"""Schema-Versioned Event Registry & Upcaster Migrations (L15 Feature 15.31)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


class SchemaValidationError(ValueError):
    """Raised when an event payload fails schema validation or version lookup."""


@dataclass
class VersionedSchema:
    """Event schema specification at a specific integer version."""

    subject: str
    version: int
    required_fields: List[str] = field(default_factory=list)
    optional_defaults: Dict[str, Any] = field(default_factory=dict)

    def validate(self, payload: Dict[str, Any]) -> None:
        missing = [f for f in self.required_fields if f not in payload]
        if missing:
            raise SchemaValidationError(
                f"{self.subject}@v{self.version} missing required fields: {missing}"
            )


UpcasterFn = Callable[[Dict[str, Any]], Dict[str, Any]]


class EventSchemaRegistry:
    """Stores versioned event schemas and executes multi-hop forward migrations."""

    def __init__(self) -> None:
        self._schemas: Dict[str, Dict[int, VersionedSchema]] = {}
        self._upcasters: Dict[Tuple[str, int, int], UpcasterFn] = {}

    def register_schema(
        self,
        subject: str,
        version: int,
        required_fields: List[str],
        optional_defaults: Optional[Dict[str, Any]] = None,
    ) -> VersionedSchema:
        schema = VersionedSchema(
            subject=subject,
            version=version,
            required_fields=list(required_fields),
            optional_defaults=dict(optional_defaults or {}),
        )
        self._schemas.setdefault(subject, {})[version] = schema
        return schema

    def register_upcaster(
        self,
        subject: str,
        from_version: int,
        to_version: int,
        fn: UpcasterFn,
    ) -> None:
        if to_version != from_version + 1:
            raise ValueError("Upcasters must advance monotonically by +1 version")
        self._upcasters[(subject, from_version, to_version)] = fn

    def latest_version(self, subject: str) -> int:
        versions = self._schemas.get(subject)
        if not versions:
            raise SchemaValidationError(f"Unknown schema subject: '{subject}'")
        return max(versions.keys())

    def migrate_and_validate(
        self,
        subject: str,
        payload: Dict[str, Any],
        source_version: int,
        target_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Upcast a vN payload to ``target_version`` (default: latest) and validate."""
        versions = self._schemas.get(subject, {})
        if source_version not in versions:
            raise SchemaValidationError(f"{subject}@v{source_version} is not registered")

        target = self.latest_version(subject) if target_version is None else target_version
        if target not in versions:
            raise SchemaValidationError(f"{subject}@v{target} is not registered")
        if target < source_version:
            raise SchemaValidationError("Downgrade consumption is unsupported")

        data = dict(payload)
        cur = source_version
        versions[cur].validate(data)
        while cur < target:
            upcaster = self._upcasters.get((subject, cur, cur + 1))
            if upcaster is not None:
                data = upcaster(dict(data))
            else:
                for k, v in versions[cur + 1].optional_defaults.items():
                    data.setdefault(k, v)
            cur += 1
        for k, v in versions[target].optional_defaults.items():
            data.setdefault(k, v)
        versions[target].validate(data)
        return data

