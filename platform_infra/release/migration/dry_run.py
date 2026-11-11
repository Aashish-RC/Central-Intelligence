"""Migration Dry-Run Engine (L17 Release - Feature 17.14).

Simulates database schema migrations against a cloned copy of schema state and
live active sessions by wiring BytebaseAdapter and MigrationRollbackGuard,
reporting predicted DDL effects without mutating live applied state.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from platform_infra.release.db.bytebase_adapter import (
    BytebaseAdapter,
    MigrationStatus,
    SchemaMigration,
)
from platform_infra.release.migration.rollback_guard import (
    ActiveSession,
    MigrationRollbackGuard,
    ValidationResult,
)


@dataclass
class StatementEffect:
    """Predicted effect of a single SQL DDL/DML statement."""

    operation: str
    target: str
    destructive: bool = False


@dataclass
class DryRunReport:
    """Comprehensive non-mutating simulation report for a schema migration."""

    migration_id: str
    database_name: str
    target_version: str
    statements_analyzed: int
    effects: List[StatementEffect] = field(default_factory=list)
    is_destructive: bool = False
    has_down_sql: bool = False
    session_validation: Optional[ValidationResult] = None
    simulated_schema_state: Dict[str, str] = field(default_factory=dict)
    applied_to_live: bool = False


class MigrationDryRunner:
    """Simulates Bytebase migrations on a sandbox copy with RollbackGuard checks."""

    def __init__(
        self,
        bytebase: Optional[BytebaseAdapter] = None,
        rollback_guard: Optional[MigrationRollbackGuard] = None,
    ) -> None:
        self.bytebase = bytebase or BytebaseAdapter()
        self.rollback_guard = rollback_guard or MigrationRollbackGuard()

    def _analyze_sql(self, sql: str) -> List[StatementEffect]:
        effects: List[StatementEffect] = []
        for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
            upper = stmt.upper()
            if m := re.match(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)", upper):
                effects.append(StatementEffect(operation="CREATE_TABLE", target=m.group(1).lower()))
            elif m := re.match(r"ALTER\s+TABLE\s+([a-zA-Z0-9_]+)\s+ADD\s+(?:COLUMN\s+)?([a-zA-Z0-9_]+)", upper):
                effects.append(StatementEffect(operation="ADD_COLUMN", target=f"{m.group(1).lower()}.{m.group(2).lower()}"))
            elif m := re.match(r"ALTER\s+TABLE\s+([a-zA-Z0-9_]+)\s+DROP\s+COLUMN\s+([a-zA-Z0-9_]+)", upper):
                effects.append(StatementEffect(operation="DROP_COLUMN", target=f"{m.group(1).lower()}.{m.group(2).lower()}", destructive=True))
            elif m := re.match(r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([a-zA-Z0-9_]+)", upper):
                effects.append(StatementEffect(operation="DROP_TABLE", target=m.group(1).lower(), destructive=True))
            else:
                op = upper.split()[0] if upper.split() else "UNKNOWN"
                effects.append(StatementEffect(operation=op, target="*", destructive=op in ("DELETE", "TRUNCATE")))
        return effects

    def dry_run(
        self,
        migration: SchemaMigration,
        active_sessions: Optional[List[ActiveSession]] = None,
    ) -> DryRunReport:
        """Simulate `migration` on a cloned schema snapshot without altering live DB state."""
        cloned_state = copy.deepcopy(self.bytebase._schema_state.get(migration.database_name, {}))
        cloned_state[migration.version] = "simulated_applied"

        effects = self._analyze_sql(migration.up_sql)
        guard_plan = self.rollback_guard.dry_run(migration)
        validation = self.rollback_guard.validate(migration, active_sessions or [])

        return DryRunReport(
            migration_id=migration.migration_id,
            database_name=migration.database_name,
            target_version=migration.version,
            statements_analyzed=len(effects),
            effects=effects,
            is_destructive=guard_plan.is_destructive or any(e.destructive for e in effects),
            has_down_sql=bool(migration.down_sql.strip()),
            session_validation=validation,
            simulated_schema_state=cloned_state,
            applied_to_live=migration.execution_status == MigrationStatus.APPLIED,
        )

