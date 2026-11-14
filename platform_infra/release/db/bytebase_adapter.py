"""Bytebase Database CI/CD Adapter (L17 Release & Lifecycle - Task 17.4).

Provides database schema change management, mandatory review gates,
automated migration execution, and reversible rollback capabilities.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    require_live_adapter,
)

logger = logging.getLogger(__name__)


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class MigrationStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class SchemaMigration:
    """A database migration unit with forward and rollback DDL scripts."""
    migration_id: str
    database_name: str
    version: str
    title: str
    up_sql: str
    down_sql: str
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    execution_status: MigrationStatus = MigrationStatus.PENDING
    reviewer: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    applied_at: Optional[float] = None
    rolled_back_at: Optional[float] = None
    applied_statements: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BytebaseAdapter:
    """Adapter for Bytebase database CI/CD and review workflows."""

    def __init__(
        self,
        endpoint_url: str = "http://localhost:8080",
        project_id: str = "central-db",
        api_token: Optional[str] = None,
        _defer_prod_check: bool = False,
    ) -> None:
        self.endpoint_url = (endpoint_url or os.getenv("BYTEBASE_LIVE_URL", "http://localhost:8080")).rstrip("/")
        self.project_id = project_id
        self.api_token = api_token or os.getenv("BYTEBASE_API_TOKEN")
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("bytebase")
        )
        self._migrations: Dict[str, SchemaMigration] = {}
        # database_name -> list of currently applied tables/columns
        self._schema_state: Dict[str, Dict[str, Any]] = {}
        self._http_client: Optional[Any] = None
        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            self._ensure_live_backend()

    def _auth_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def _get_client(self) -> Any:
        if self._http_client is None:
            import httpx
            self._http_client = httpx.Client(timeout=120.0)
        return self._http_client

    def _ensure_live_backend(self) -> None:
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            return
        if not self.api_token:
            fail_closed_in_production(
                "bytebase",
                "BYTEBASE_API_TOKEN not set; required for live mode",
            )
        try:
            import httpx
            resp = httpx.get(
                f"{self.endpoint_url}/v1/projects/{self.project_id}",
                headers=self._auth_headers(),
                timeout=5.0,
            )
            if resp.status_code not in (200, 404):
                fail_closed_in_production(
                    "bytebase",
                    f"Bytebase server returned HTTP {resp.status_code}",
                )
            self._http_client = httpx.Client(timeout=120.0)
        except ProductionSafetyError:
            raise
        except Exception as exc:
            fail_closed_in_production(
                "bytebase",
                f"Bytebase at {self.endpoint_url} unreachable: {exc}",
                cause=exc,
            )

    def create_migration(
        self,
        database_name: str,
        version: str,
        title: str,
        up_sql: str,
        down_sql: str,
    ) -> SchemaMigration:
        """Create a new migration awaiting mandatory peer/CI review."""
        migration_id = f"mig_{version}_{uuid.uuid4().hex[:6]}"
        migration = SchemaMigration(
            migration_id=migration_id,
            database_name=database_name,
            version=version,
            title=title,
            up_sql=up_sql,
            down_sql=down_sql,
            review_status=ReviewStatus.PENDING_REVIEW,
            execution_status=MigrationStatus.PENDING,
        )
        self._migrations[migration_id] = migration

        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            try:
                client = self._http_client or self._get_client()
                resp = client.post(
                    f"{self.endpoint_url}/v1/projects/{self.project_id}/issues",
                    json={
                        "title": title,
                        "database": database_name,
                        "sql": up_sql,
                        "rollbackSql": down_sql,
                        "type": "bb.issue.database.schema.update",
                    },
                    headers=self._auth_headers(),
                    timeout=10.0,
                )
                if resp.status_code not in (200, 201):
                    fail_closed_in_production(
                        "bytebase",
                        f"Bytebase create issue HTTP {resp.status_code}: {resp.text}",
                    )
                migration.metadata = migration.metadata or {}
                migration.metadata["bytebase_issue_id"] = resp.json().get("name", "")
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production(
                    "bytebase",
                    f"Bytebase create_migration failed: {exc}",
                    cause=exc,
                )

        logger.info("Created schema migration %s awaiting review", migration_id)
        return migration

    def review_migration(
        self,
        migration_id: str,
        approved: bool,
        reviewer: str,
        comments: Optional[str] = None,
    ) -> SchemaMigration:
        """Review gate: Approve or reject migration before deployment."""
        migration = self._migrations.get(migration_id)
        if not migration:
            raise ValueError(f"Migration not found: {migration_id}")

        migration.review_status = ReviewStatus.APPROVED if approved else ReviewStatus.REJECTED
        migration.reviewer = reviewer
        logger.info("Migration %s review updated: %s by %s", migration_id, migration.review_status.value, reviewer)
        return migration

    def apply_migration(self, migration_id: str) -> SchemaMigration:
        """Apply approved migration to database."""
        migration = self._migrations.get(migration_id)
        if not migration:
            raise ValueError(f"Migration not found: {migration_id}")

        if migration.review_status != ReviewStatus.APPROVED:
            raise PermissionError(
                f"Cannot apply migration '{migration_id}': review status is '{migration.review_status.value}', requires 'approved'"
            )

        if migration.execution_status == MigrationStatus.APPLIED:
            return migration

        # Hermetic / simulated path — preserves existing test contract
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            statements = [s.strip() for s in migration.up_sql.split(";") if s.strip()]
            migration.applied_statements = statements
            migration.execution_status = MigrationStatus.APPLIED
            migration.applied_at = time.time()
            self._schema_state.setdefault(migration.database_name, {})[migration.version] = "applied"
            logger.info("Successfully applied migration %s (%d statements)", migration_id, len(statements))
            return migration

        # Live path — execute SQL via Bytebase
        try:
            client = self._http_client or self._get_client()
            resp = client.post(
                f"{self.endpoint_url}/v1/sql/execute",
                json={
                    "instance": migration.database_name,
                    "database": migration.database_name,
                    "sql": migration.up_sql,
                    "statement": migration.up_sql,
                },
                headers=self._auth_headers(),
                timeout=120.0,
            )
            if resp.status_code not in (200, 201):
                migration.execution_status = MigrationStatus.FAILED
                fail_closed_in_production(
                    "bytebase",
                    f"Bytebase apply HTTP {resp.status_code}: {resp.text}",
                )
            migration.applied_statements = [migration.up_sql]
            migration.execution_status = MigrationStatus.APPLIED
            migration.applied_at = time.time()
            self._schema_state.setdefault(migration.database_name, {})[migration.version] = "applied"
            logger.info("Successfully applied live migration %s via Bytebase", migration_id)
            return migration
        except ProductionSafetyError:
            raise
        except Exception as exc:
            migration.execution_status = MigrationStatus.FAILED
            fail_closed_in_production(
                "bytebase",
                f"Bytebase apply_migration failed: {exc}",
                cause=exc,
            )

    def rollback_migration(self, migration_id: str) -> SchemaMigration:
        """Roll back an applied migration using its down_sql."""
        migration = self._migrations.get(migration_id)
        if not migration:
            raise ValueError(f"Migration not found: {migration_id}")

        if migration.execution_status != MigrationStatus.APPLIED:
            raise ValueError(f"Cannot rollback migration with status '{migration.execution_status.value}'")

        # Hermetic / simulated path
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            statements = [s.strip() for s in migration.down_sql.split(";") if s.strip()]
            migration.execution_status = MigrationStatus.ROLLED_BACK
            migration.rolled_back_at = time.time()
            if migration.database_name in self._schema_state:
                self._schema_state[migration.database_name].pop(migration.version, None)
            logger.info("Successfully rolled back migration %s", migration_id)
            return migration

        # Live path
        try:
            client = self._http_client or self._get_client()
            resp = client.post(
                f"{self.endpoint_url}/v1/sql/execute",
                json={
                    "instance": migration.database_name,
                    "database": migration.database_name,
                    "sql": migration.down_sql,
                    "statement": migration.down_sql,
                },
                headers=self._auth_headers(),
                timeout=120.0,
            )
            if resp.status_code not in (200, 201):
                migration.execution_status = MigrationStatus.FAILED
                fail_closed_in_production(
                    "bytebase",
                    f"Bytebase rollback HTTP {resp.status_code}: {resp.text}",
                )
            migration.execution_status = MigrationStatus.ROLLED_BACK
            migration.rolled_back_at = time.time()
            if migration.database_name in self._schema_state:
                self._schema_state[migration.database_name].pop(migration.version, None)
            logger.info("Successfully rolled back live migration %s via Bytebase", migration_id)
            return migration
        except ProductionSafetyError:
            raise
        except Exception as exc:
            migration.execution_status = MigrationStatus.FAILED
            fail_closed_in_production(
                "bytebase",
                f"Bytebase rollback_migration failed: {exc}",
                cause=exc,
            )

    def get_migration(self, migration_id: str) -> Optional[SchemaMigration]:
        return self._migrations.get(migration_id)

    def is_version_applied(self, database_name: str, version: str) -> bool:
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            return self._schema_state.get(database_name, {}).get(version) == "applied"

        client = self._http_client or self._get_client()
        try:
            resp = client.get(
                f"{self.endpoint_url}/v1/instances/{database_name}/databases/{database_name}/schema",
                headers=self._auth_headers(),
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                applied = data.get("applied_versions", []) or [m.get("version") for m in data.get("migrations", [])]
                if version in applied:
                    return True
            return self._schema_state.get(database_name, {}).get(version) == "applied"
        except Exception as exc:
            logger.warning("Bytebase schema check error: %s", exc)
            return self._schema_state.get(database_name, {}).get(version) == "applied"
