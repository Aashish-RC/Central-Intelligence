"""SQLite Plan Store: Persistent checkpointing, node status updates, and resumption."""

from datetime import datetime
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, List, Optional
from ..core.interfaces import BasePlanStore
from ..core.models import (
    PlanDAG,
    PlanNode,
    TaskStatus,
    utc_now,
)


class SQLitePlanStore(BasePlanStore):
    """Local SQLite engine managing persistent plan DAG states and checkpoint snapshots."""

    def __init__(self, db_path: str = "./orchestrator.db"):
        self._db_path = db_path
        self._memory_conn: Optional[sqlite3.Connection] = None
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row

        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        from storage.migrations import SchemaMigrator, Migration, add_column_if_missing
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orchestrator_plans (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    project_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    budget_limit REAL NOT NULL,
                    max_concurrency INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            def _migrate_v1_tables_and_indexes(c: sqlite3.Connection):
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_plans_project
                    ON orchestrator_plans(project_id);
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS orchestrator_nodes (
                        id TEXT PRIMARY KEY,
                        plan_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        action TEXT NOT NULL,
                        params TEXT NOT NULL,
                        depends_on TEXT NOT NULL,
                        status TEXT NOT NULL,
                        cost_estimate REAL NOT NULL,
                        output TEXT,
                        error TEXT,
                        duration_ms REAL NOT NULL DEFAULT 0.0,
                        FOREIGN KEY(plan_id) REFERENCES orchestrator_plans(id) ON DELETE CASCADE
                    );
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_nodes_plan
                    ON orchestrator_nodes(plan_id);
                """)

            def _migrate_v2_tenant_id(c: sqlite3.Connection):
                add_column_if_missing(c, "orchestrator_plans", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_plans_tenant
                    ON orchestrator_plans(tenant_id);
                """)

            migrator = SchemaMigrator(conn)
            migrator.apply_all([
                Migration(version=1, name="initial_orchestrator_tables", up=_migrate_v1_tables_and_indexes),
                Migration(version=2, name="orchestrator_plans_tenant_id", up=_migrate_v2_tenant_id),
            ])
            conn.commit()
            if self._memory_conn is None:
                conn.close()

    def save_plan(self, plan: PlanDAG) -> None:
        now = utc_now().isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO orchestrator_plans (
                        id, tenant_id, project_id, title, status, budget_limit, max_concurrency, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        tenant_id = excluded.tenant_id,
                        status = excluded.status,
                        updated_at = excluded.updated_at
                    """,
                    (
                        plan.id,
                        getattr(plan, "tenant_id", "default") or "default",
                        plan.project_id,
                        plan.title,
                        plan.status.value,
                        plan.budget_limit,
                        plan.max_concurrency,
                        plan.created_at.isoformat(),
                        now,
                    ),
                )
                for node in plan.nodes.values():
                    conn.execute(
                        """
                        INSERT INTO orchestrator_nodes (
                            id, plan_id, title, action, params, depends_on, status, cost_estimate, output, error, duration_ms
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            status = excluded.status,
                            output = excluded.output,
                            error = excluded.error,
                            duration_ms = excluded.duration_ms
                        """,
                        (
                            node.id,
                            plan.id,
                            node.title,
                            node.action,
                            json.dumps(node.params),
                            json.dumps(node.depends_on),
                            node.status.value,
                            node.cost_estimate,
                            json.dumps(node.output) if node.output is not None else None,
                            node.error,
                            node.duration_ms,
                        ),
                    )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_plan(
        self,
        plan_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[PlanDAG]:
        with self._lock:
            conn = self._get_connection()
            try:
                query = "SELECT * FROM orchestrator_plans WHERE id = ?"
                params: list = [plan_id]
                if tenant_id:
                    query += " AND tenant_id = ?"
                    params.append(tenant_id)
                cur = conn.execute(query, params)
                p_row = cur.fetchone()
                if not p_row:
                    return None

                n_cur = conn.execute("SELECT * FROM orchestrator_nodes WHERE plan_id = ?", (plan_id,))
                nodes = {}
                for r in n_cur.fetchall():
                    raw_out = r["output"]
                    out = json.loads(raw_out) if raw_out is not None else None
                    node = PlanNode(
                        id=r["id"],
                        tenant_id=getattr(p_row, "tenant_id", "default") if "tenant_id" in p_row.keys() else "default",
                        title=r["title"],
                        action=r["action"],
                        params=json.loads(r["params"]),
                        depends_on=json.loads(r["depends_on"]),
                        status=TaskStatus(r["status"]),
                        cost_estimate=float(r["cost_estimate"]),
                        output=out,
                        error=r["error"],
                        duration_ms=float(r["duration_ms"]),
                    )
                    nodes[node.id] = node

                return PlanDAG(
                    id=p_row["id"],
                    tenant_id=p_row["tenant_id"] if "tenant_id" in p_row.keys() else "default",
                    project_id=p_row["project_id"],
                    title=p_row["title"],
                    status=TaskStatus(p_row["status"]),
                    budget_limit=float(p_row["budget_limit"]),
                    max_concurrency=int(p_row["max_concurrency"]),
                    nodes=nodes,
                    created_at=datetime.fromisoformat(p_row["created_at"]),
                    updated_at=datetime.fromisoformat(p_row["updated_at"]),
                )
            finally:
                if self._memory_conn is None:
                    conn.close()

    def update_node(
        self,
        plan_id: str,
        node_id: str,
        status: TaskStatus,
        output: Any = None,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
    ) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    UPDATE orchestrator_nodes
                    SET status = ?, output = ?, error = ?, duration_ms = ?
                    WHERE id = ? AND plan_id = ?
                    """,
                    (
                        status.value,
                        json.dumps(output) if output is not None else None,
                        error,
                        duration_ms,
                        node_id,
                        plan_id,
                    ),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()

    def update_plan_status(self, plan_id: str, status: TaskStatus) -> None:
        now = utc_now().isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    UPDATE orchestrator_plans
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status.value, now, plan_id),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()

    def list_plans(
        self,
        project_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[PlanDAG]:
        with self._lock:
            conn = self._get_connection()
            try:
                query = "SELECT id FROM orchestrator_plans WHERE 1=1"
                params: list = []
                if tenant_id:
                    query += " AND tenant_id = ?"
                    params.append(tenant_id)
                if project_id:
                    query += " AND project_id = ?"
                    params.append(project_id)
                query += " ORDER BY updated_at DESC"
                cur = conn.execute(query, params)
                plan_ids = [r["id"] for r in cur.fetchall()]
            finally:
                if self._memory_conn is None:
                    conn.close()

        plans = []
        for pid in plan_ids:
            p = self.get_plan(pid)
            if p:
                plans.append(p)
        return plans

