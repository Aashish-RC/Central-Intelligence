"""Schema Migration Rollback Guard (L17 Release & Lifecycle - Tasks 17.08, 17.13-17.15).

Dry-run validator that checks backward compatibility with active live sessions
before database migrations are applied. Blocks destructive schema migrations
(e.g., dropping columns or tables actively read by existing sessions) to guarantee zero errors.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ActiveSession:
    """Represents an active, in-flight conversational or client session."""
    session_id: str
    schema_version: str
    accessed_tables: Set[str] = field(default_factory=set)
    accessed_columns: Set[str] = field(default_factory=set)


@dataclass
class MigrationPlan:
    """Schema change representation analyzed from DDL."""
    migration_id: str
    target_version: str
    sql: str
    dropped_tables: Set[str] = field(default_factory=set)
    dropped_columns: Set[str] = field(default_factory=set)  # format: "table.column"
    added_columns: Set[str] = field(default_factory=set)
    is_destructive: bool = False


@dataclass
class ValidationResult:
    """Result of backward compatibility validation against active sessions."""
    safe: bool
    reason: str = "Migration is backward-compatible with all active sessions"
    breaking_sessions: List[str] = field(default_factory=list)
    dry_run_details: Dict[str, Any] = field(default_factory=dict)


class MigrationRollbackGuard:
    """Dry-run validation engine for safe schema migrations."""

    def dry_run(self, migration: Any) -> MigrationPlan:
        """Parse and simulate migration DDL to detect destructive mutations."""
        if isinstance(migration, MigrationPlan):
            return migration

        # Extract SQL string from Bytebase SchemaMigration or string
        sql = getattr(migration, "up_sql", str(migration))
        mig_id = getattr(migration, "migration_id", "dry_run_mig")
        ver = getattr(migration, "version", "next")

        plan = MigrationPlan(migration_id=mig_id, target_version=ver, sql=sql)

        # Regex heuristics for destructive DDL
        # 1. DROP TABLE [IF EXISTS] <table>
        drop_table_matches = re.findall(
            r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([a-zA-Z0-9_]+)",
            sql,
            re.IGNORECASE,
        )
        for t in drop_table_matches:
            plan.dropped_tables.add(t.lower())
            plan.is_destructive = True

        # 2. ALTER TABLE <table> DROP COLUMN <column>
        drop_col_matches = re.findall(
            r"ALTER\s+TABLE\s+([a-zA-Z0-9_]+)\s+DROP\s+COLUMN\s+([a-zA-Z0-9_]+)",
            sql,
            re.IGNORECASE,
        )
        for t, c in drop_col_matches:
            plan.dropped_columns.add(f"{t.lower()}.{c.lower()}")
            plan.is_destructive = True

        return plan

    def is_compatible(self, dry_result: MigrationPlan, session: ActiveSession) -> tuple[bool, Optional[str]]:
        """Check if an individual active session will be broken by the migration."""
        # Check dropped tables
        for table in session.accessed_tables:
            if table.lower() in dry_result.dropped_tables:
                return False, f"Table '{table}' dropped by migration is required by session '{session.session_id}'"

        # Check dropped columns
        for col in session.accessed_columns:
            if col.lower() in dry_result.dropped_columns:
                return False, f"Column '{col}' dropped by migration is required by session '{session.session_id}'"

        return True, None

    def validate(self, migration: Any, active_sessions: List[ActiveSession]) -> ValidationResult:
        """Validate migration compatibility against all active sessions.

        Algorithm:
        - dry_result = self.dry_run(migration)
        - for session in active_sessions:
        -     if not self.is_compatible(dry_result, session):
        -         return ValidationResult(safe=False, reason=f"Breaks session {session.session_id}")
        - return ValidationResult(safe=True)
        """
        dry_result = self.dry_run(migration)
        breaking: List[str] = []
        first_failure_reason: Optional[str] = None

        for session in active_sessions:
            compatible, reason = self.is_compatible(dry_result, session)
            if not compatible:
                breaking.append(session.session_id)
                if not first_failure_reason:
                    first_failure_reason = f"Breaks session {session.session_id}: {reason}"

        if breaking:
            return ValidationResult(
                safe=False,
                reason=first_failure_reason or f"Breaks {len(breaking)} active session(s)",
                breaking_sessions=breaking,
                dry_run_details={
                    "dropped_tables": list(dry_result.dropped_tables),
                    "dropped_columns": list(dry_result.dropped_columns),
                },
            )

        return ValidationResult(
            safe=True,
            reason="All active sessions compatible",
            dry_run_details={
                "destructive": dry_result.is_destructive,
            },
        )
