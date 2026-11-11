"""Tests for EventSchemaRegistry (L15 Feature 15.31)."""

from __future__ import annotations

import pytest

from platform_infra.data.messaging.schema_registry import (
    EventSchemaRegistry,
    SchemaValidationError,
)


def test_schema_registry_v1_to_v2_migration() -> None:
    reg = EventSchemaRegistry()
    reg.register_schema("user.created", 1, required_fields=["user_id"])
    reg.register_schema("user.created", 2, required_fields=["user_id", "tenant_id"])
    reg.register_upcaster(
        "user.created",
        1,
        2,
        lambda p: {**p, "tenant_id": p.get("org", "default-tenant")},
    )

    migrated = reg.migrate_and_validate("user.created", {"user_id": "u1"}, source_version=1)
    assert migrated == {"user_id": "u1", "tenant_id": "default-tenant"}

    with pytest.raises(SchemaValidationError):
        reg.migrate_and_validate("user.created", {}, source_version=1)

