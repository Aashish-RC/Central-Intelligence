"""
Append-only, tamper-evident unified audit ledger with cryptographic hashing.
"""

import json
import sqlite3
import threading
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .models import UnifiedAuditEntry, AuditSeverity, UserRole


class UnifiedAuditLedger:
    """Tamper-evident append-only ledger for all cross-module audit events."""

    def __init__(self, db_path: str = "./data/unified_audit.db"):
        self._db_path = db_path
        self._memory_conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS unified_audit_log (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    project_id TEXT NOT NULL DEFAULT 'default',
                    user_id TEXT,
                    role TEXT NOT NULL DEFAULT 'system',
                    module TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'success',
                    severity TEXT NOT NULL DEFAULT 'info',
                    details_json TEXT NOT NULL DEFAULT '{}',
                    client_ip TEXT,
                    timestamp TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_tenant_time
                ON unified_audit_log(tenant_id, timestamp DESC);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_module_action
                ON unified_audit_log(module, action);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_user_role
                ON unified_audit_log(user_id, role);
            """)
            conn.commit()
            if self._memory_conn is None:
                conn.close()

    def _get_latest_hash(self, conn: sqlite3.Connection) -> str:
        cur = conn.execute("SELECT entry_hash FROM unified_audit_log ORDER BY seq DESC LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else "GENESIS_HASH_PHEONIX_2026"

    def _calculate_hash(self, prev_hash: str, entry: UnifiedAuditEntry, details_json: str) -> str:
        payload = (
            f"{prev_hash}|{entry.id}|{entry.tenant_id}|{entry.project_id}|"
            f"{entry.user_id or ''}|{entry.role}|{entry.module}|{entry.action}|"
            f"{entry.resource}|{entry.status}|{entry.severity.value}|"
            f"{details_json}|{entry.timestamp.isoformat()}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def log(self, entry: UnifiedAuditEntry) -> str:
        """Appends an immutable audit entry into the cryptographically chained ledger."""
        details_json = json.dumps(entry.details, sort_keys=True)
        with self._lock:
            conn = self._get_connection()
            try:
                prev_hash = self._get_latest_hash(conn)
                entry_hash = self._calculate_hash(prev_hash, entry, details_json)
                role_val = entry.role.value if hasattr(entry.role, "value") else str(entry.role)
                severity_val = entry.severity.value if hasattr(entry.severity, "value") else str(entry.severity)

                conn.execute(
                    """
                    INSERT INTO unified_audit_log (
                        id, tenant_id, project_id, user_id, role, module, action, resource,
                        status, severity, details_json, client_ip, timestamp, prev_hash, entry_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.tenant_id,
                        entry.project_id,
                        entry.user_id,
                        role_val,
                        entry.module,
                        entry.action,
                        entry.resource,
                        entry.status,
                        severity_val,
                        details_json,
                        entry.client_ip,
                        entry.timestamp.isoformat(),
                        prev_hash,
                        entry_hash,
                    ),
                )
                conn.commit()
                return entry_hash
            finally:
                if self._memory_conn is None:
                    conn.close()

    def query(
        self,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        role: Optional[Union[UserRole, str]] = None,
        module: Optional[str] = None,
        action: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[UnifiedAuditEntry]:
        """Query audit log entries with multi-tenant and role filtering."""
        conditions = []
        params: List[Any] = []

        if tenant_id:
            conditions.append("tenant_id = ?")
            params.append(tenant_id)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if role:
            role_val = role.value if hasattr(role, "value") else str(role)
            conditions.append("role = ?")
            params.append(role_val)
        if module:
            conditions.append("module = ?")
            params.append(module)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        query_sql = f"""
            SELECT id, tenant_id, project_id, user_id, role, module, action, resource,
                   status, severity, details_json, client_ip, timestamp
            FROM unified_audit_log{where_clause}
            ORDER BY seq DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(query_sql, params)
                rows = cur.fetchall()
                entries = []
                for r in rows:
                    details = json.loads(r["details_json"]) if r["details_json"] else {}
                    entries.append(
                        UnifiedAuditEntry(
                            id=r["id"],
                            tenant_id=r["tenant_id"],
                            project_id=r["project_id"],
                            user_id=r["user_id"],
                            role=r["role"],
                            module=r["module"],
                            action=r["action"],
                            resource=r["resource"],
                            status=r["status"],
                            severity=AuditSeverity(r["severity"]),
                            details=details,
                            client_ip=r["client_ip"],
                            timestamp=datetime.fromisoformat(r["timestamp"]),
                        )
                    )
                return entries
            finally:
                if self._memory_conn is None:
                    conn.close()

    def count(self, tenant_id: Optional[str] = None, module: Optional[str] = None) -> int:
        """Count matching records in the ledger."""
        conditions = []
        params: List[Any] = []
        if tenant_id:
            conditions.append("tenant_id = ?")
            params.append(tenant_id)
        if module:
            conditions.append("module = ?")
            params.append(module)
        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT COUNT(*) FROM unified_audit_log{where_clause}"

        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(sql, params)
                return cur.fetchone()[0]
            finally:
                if self._memory_conn is None:
                    conn.close()

    def verify_integrity(self) -> bool:
        """Validates that no record in the audit ledger has been modified or tampered with."""
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    """
                    SELECT id, tenant_id, project_id, user_id, role, module, action, resource,
                           status, severity, details_json, timestamp, prev_hash, entry_hash
                    FROM unified_audit_log
                    ORDER BY seq ASC
                    """
                )
                rows = cur.fetchall()
                expected_prev_hash = "GENESIS_HASH_PHEONIX_2026"
                for r in rows:
                    if r["prev_hash"] != expected_prev_hash:
                        return False
                    
                    entry = UnifiedAuditEntry(
                        id=r["id"],
                        tenant_id=r["tenant_id"],
                        project_id=r["project_id"],
                        user_id=r["user_id"],
                        role=r["role"],
                        module=r["module"],
                        action=r["action"],
                        resource=r["resource"],
                        status=r["status"],
                        severity=AuditSeverity(r["severity"]),
                        details=json.loads(r["details_json"]),
                        timestamp=datetime.fromisoformat(r["timestamp"]),
                    )
                    recomputed_hash = self._calculate_hash(expected_prev_hash, entry, r["details_json"])
                    if recomputed_hash != r["entry_hash"]:
                        return False
                    expected_prev_hash = r["entry_hash"]
                return True
            finally:
                if self._memory_conn is None:
                    conn.close()

    def verify_chain(self) -> bool:
        """Alias for verify_integrity for automated cryptographic chain verification."""
        return self.verify_integrity()

