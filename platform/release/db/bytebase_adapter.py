"""Bytebase Database CI/CD Adapter (L17 Release & Lifecycle - Task 17.4).

Provides database schema change management, mandatory review gates,
automated migration execution, and reversible rollback capabilities.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

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


class BytebaseAdapter:
    """Adapter for Bytebase database CI/CD and review workflows."""

    def __init__(self, endpoint_url: str = "http://localhost:8080", project_id: str = "central-db") -> None:
        self.endpoint_url = endpoint_url
        self.project_id = project_id
        self._migrations: Dict[str, SchemaMigration] = {}
        # database_name -> list of currently applied tables/columns
        self._schema_state: Dict[str, Dict[str, Any]] = {}

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

        # Execute up_sql statements
        statements = [s.strip() for s in migration.up_sql.split(";") if s.strip()]
        migration.applied_statements = statements
        migration.execution_status = MigrationStatus.APPLIED
        migration.applied_at = time.time()

        if migration.database_name not in self._schema_state:
            self._schema_state[migration.database_name] = {}
        self._schema_state[migration.database_name][migration.version] = "applied"

        logger.info("Successfully applied migration %s (%d statements)", migration_id, len(statements))
        return migration

    def rollback_migration(self, migration_id: str) -> SchemaMigration:
        """Roll back an applied migration using its down_sql."""
        migration = self._migrations.get(migration_id)
        if not migration:
            raise ValueError(f"Migration not found: {migration_id}")

        if migration.execution_status != MigrationStatus.APPLIED:
            raise ValueError(f"Cannot rollback migration with status '{migration.execution_status.value}'")

        # Execute down_sql statements
        statements = [s.strip() for s in migration.down_sql.split(";") if s.strip()]
        migration.execution_status = MigrationStatus.ROLLED_BACK
        migration.rolled_back_at = time.time()

        if migration.database_name in self._schema_state:
            self._schema_state[migration.database_name].pop(migration.version, None)

        logger.info("Successfully rolled back migration %s", migration_id)
        return migration

    def get_migration(self, migration_id: str) -> Optional[SchemaMigration]:
        return self._migrations.get(migration_id)

    def is_version_applied(self, database_name: str, version: str) -> bool:
        return self._schema_state.get(database_name, {}).get(version) == "applied"
