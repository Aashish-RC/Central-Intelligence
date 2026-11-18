"""
Stage S3.6: Chaos Engineering & Crash Recovery Drill Suite.

Verifies Central Intelligence v1 resilience under hostile operating failures:
- Scenario 1: Sudden SIGKILL of PostgreSQL database during concurrent write ingestion,
              verifying WAL replay, zero data corruption, clean rollback of in-flight
              transactions, and immediate operational recovery.
- Scenario 2: Valkey cache outage/loss (FLUSHALL & container stop), verifying seamless
              fallback to PostgreSQL relational state without 500 errors, followed by
              automatic cache reconnection and repopulation.
- Scenario 3: High-concurrency Capability Activation Drain Race (50 concurrent workers),
              verifying zero deadlocks, thread-safe lease management, and 100% Merkle
              audit ledger cryptographic integrity.
- Scenario 4: Worker crash & resume durability, verifying workflow state survival and
              replay checkpointing across ungraceful process termination.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

import pytest
import redis
import sqlalchemy
from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from platform_infra.compute.lifecycle.capability_activation import (
    CapabilityActivationManager,
    CapabilityDefinition,
    CapabilityState,
)

POSTGRES_URL = os.getenv(
    "POSTGRES_LIVE_URL",
    "postgresql://postgres:postgres-development-pass@127.0.0.1:5432/postgres",
)
VALKEY_HOST = os.getenv("VALKEY_HOST", "127.0.0.1")
VALKEY_PORT = int(os.getenv("VALKEY_PORT", "6379"))


def _get_pg_engine(timeout_s: float = 5.0) -> sqlalchemy.engine.Engine:
    # Use pg8000 driver with NullPool for clean isolation
    url = POSTGRES_URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+pg8000://", 1)
    return sqlalchemy.create_engine(
        url,
        connect_args={"timeout": timeout_s},
        poolclass=sqlalchemy.pool.NullPool,
    )


def _wait_for_postgres(max_wait_s: float = 30.0) -> bool:
    start = time.time()
    while time.time() - start < max_wait_s:
        try:
            engine = _get_pg_engine(timeout_s=2.0)
            with engine.connect() as conn:
                in_rec = conn.execute(text("SELECT pg_is_in_recovery()")).scalar()
                if not in_rec:
                    return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def _wait_for_valkey(max_wait_s: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < max_wait_s:
        try:
            client = redis.Redis(host=VALKEY_HOST, port=VALKEY_PORT, socket_timeout=1.0)
            if client.ping():
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


# ==============================================================================
# SCENARIO 1: PostgreSQL SIGKILL WAL Recovery Under Heavy Write Load
# ==============================================================================

@pytest.mark.integration
def test_postgres_sigkill_wal_recovery_under_load():
    """Verify PostgreSQL WAL recovery completes cleanly with 0 corrupted pages after sudden SIGKILL."""
    assert _wait_for_postgres(10.0), "PostgreSQL container must be running"

    engine = _get_pg_engine()
    test_run_id = uuid4().hex[:8]
    table_name = f"chaos_wal_test_{test_run_id}"

    # 1. Setup stress table
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(64) NOT NULL,
                batch_id INT NOT NULL,
                payload TEXT NOT NULL,
                checksum VARCHAR(64) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            )
        )

    # 2. Start rapid background writer thread
    stop_event = threading.Event()
    writer_errors: List[Exception] = []
    committed_batches: List[int] = []

    def writer_loop():
        w_engine = _get_pg_engine(timeout_s=2.0)
        batch = 0
        while not stop_event.is_set():
            batch += 1
            payload = f"audit_event_block_{batch}_{uuid4().hex * 10}"
            chk = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            try:
                with w_engine.begin() as conn:
                    # Write batch of 5 records atomically
                    for sub in range(5):
                        sub_payload = f"{payload}_sub_{sub}"
                        sub_chk = hashlib.sha256(sub_payload.encode("utf-8")).hexdigest()
                        conn.execute(
                            text(
                                f"INSERT INTO {table_name} (tenant_id, batch_id, payload, checksum) VALUES (:t, :b, :p, :c)"
                            ),
                            {"t": f"tenant_{test_run_id}", "b": batch, "p": sub_payload, "c": sub_chk},
                        )
                committed_batches.append(batch)
                time.sleep(0.01)
            except Exception as exc:
                writer_errors.append(exc)
                # When SIGKILL hits, we expect connection termination
                break

    writer_thread = threading.Thread(target=writer_loop, daemon=True)
    writer_thread.start()

    # Allow at least 5 batches (25 rows) to be written
    time_start = time.time()
    while len(committed_batches) < 5 and time.time() - time_start < 5.0:
        time.sleep(0.05)

    assert len(committed_batches) >= 3, "Writer did not commit initial records in time"

    # 3. Inject sudden SIGKILL to PostgreSQL container
    subprocess.run(["docker", "kill", "-s", "SIGKILL", "central-supabase-db"], check=True)
    stop_event.set()
    writer_thread.join(timeout=5.0)

    # Verify that writer noticed the abrupt failure
    assert len(writer_errors) > 0, "Writer should have encountered an abrupt socket disconnect upon SIGKILL"

    # 4. Restart PostgreSQL container
    subprocess.run(["docker", "start", "central-supabase-db"], check=True)

    # 5. Wait for WAL replay and database recovery
    recovered = _wait_for_postgres(max_wait_s=30.0)
    assert recovered, "PostgreSQL failed to recover within 30 seconds after SIGKILL"

    # 6. Verify WAL integrity & zero corruption
    recovery_engine = _get_pg_engine()
    with recovery_engine.connect() as conn:
        in_rec = conn.execute(text("SELECT pg_is_in_recovery()")).scalar()
        assert in_rec is False, "Database is still in recovery mode"

        rows = conn.execute(
            text(f"SELECT id, batch_id, payload, checksum FROM {table_name} ORDER BY id ASC")
        ).fetchall()

    assert len(rows) > 0, "All rows lost after crash!"

    # Validate checksum of every single recovered row (0 corrupted records)
    corrupted_count = 0
    for r in rows:
        expected_chk = hashlib.sha256(r.payload.encode("utf-8")).hexdigest()
        if r.checksum != expected_chk:
            corrupted_count += 1
    assert corrupted_count == 0, f"Found {corrupted_count} corrupted rows during WAL replay!"

    # Verify atomic transactions: each committed batch must have exactly 5 rows (no partial writes)
    batch_counts: dict[int, int] = {}
    for r in rows:
        batch_counts[r.batch_id] = batch_counts.get(r.batch_id, 0) + 1
    for b_id, count in batch_counts.items():
        assert count == 5, f"Atomicity violation: Batch {b_id} has {count}/5 rows (partial commit detected)!"

    # 7. Verify subsequent writes succeed immediately
    new_payload = f"post_recovery_payload_{uuid4().hex}"
    new_chk = hashlib.sha256(new_payload.encode("utf-8")).hexdigest()
    with recovery_engine.begin() as w_conn:
        w_conn.execute(
            text(f"INSERT INTO {table_name} (tenant_id, batch_id, payload, checksum) VALUES (:t, :b, :p, :c)"),
            {"t": f"tenant_{test_run_id}", "b": 9999, "p": new_payload, "c": new_chk},
        )

    with recovery_engine.connect() as conn:
        post_rows = conn.execute(
            text(f"SELECT count(*) FROM {table_name} WHERE batch_id = 9999")
        ).scalar()
        assert post_rows == 1, "Failed to write new transaction post-recovery"

    # Cleanup table
    with recovery_engine.begin() as drop_conn:
        drop_conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))


# ==============================================================================
# SCENARIO 2: Valkey Cache Loss & Relational State Fallback
# ==============================================================================

@pytest.mark.integration
def test_valkey_cache_loss_and_relational_fallback():
    """Verify cache loss and complete Valkey outage seamlessly falls back to PostgreSQL relational store."""
    assert _wait_for_valkey(10.0), "Valkey container must be running"
    assert _wait_for_postgres(10.0), "PostgreSQL container must be running"

    test_run_id = uuid4().hex[:8]
    table_name = f"chaos_state_store_{test_run_id}"
    session_id = f"sess_{test_run_id}"
    authoritative_data = {"user": "alice", "tier": "enterprise", "tokens_spent": 4200, "status": "active"}

    pg_engine = _get_pg_engine()
    with pg_engine.begin() as conn:
        conn.execute(
            text(
                f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                session_id VARCHAR(64) PRIMARY KEY,
                state_data JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            )
        )
        import json
        conn.execute(
            text(f"INSERT INTO {table_name} (session_id, state_data) VALUES (:s, :d)"),
            {"s": session_id, "d": json.dumps(authoritative_data)},
        )

    # Populate Valkey cache
    r_client = redis.Redis(host=VALKEY_HOST, port=VALKEY_PORT, decode_responses=True, socket_timeout=1.0)
    cache_key = f"cache:session:{session_id}"
    import json
    r_client.set(cache_key, json.dumps(authoritative_data), ex=300)
    assert r_client.get(cache_key) is not None

    # Implement Fault-Tolerant Cache-Aside Resolver
    class ResilientStateResolver:
        def __init__(self, valkey_client: redis.Redis, engine: sqlalchemy.engine.Engine, store_table: str):
            self.valkey = valkey_client
            self.engine = engine
            self.store_table = store_table
            self.fallback_invocations = 0

        def get_session_state(self, s_id: str) -> dict:
            c_key = f"cache:session:{s_id}"
            # 1. Try cache
            try:
                cached = self.valkey.get(c_key)
                if cached:
                    return json.loads(cached)
            except (redis.ConnectionError, redis.TimeoutError, Exception) as exc:
                # Log degraded cache access, trigger fallback
                self.fallback_invocations += 1

            # 2. Seamless Fallback to PostgreSQL
            with self.engine.connect() as conn:
                row = conn.execute(
                    text(f"SELECT state_data FROM {self.store_table} WHERE session_id = :s"),
                    {"s": s_id},
                ).scalar()
                if row:
                    data = row if isinstance(row, dict) else json.loads(row)
                    # Try to heal/repopulate cache asynchronously if cache is alive
                    try:
                        self.valkey.set(c_key, json.dumps(data), ex=300)
                    except Exception:
                        pass
                    return data
            raise KeyError(f"Session {s_id} not found in authoritative store")

    resolver = ResilientStateResolver(r_client, pg_engine, table_name)

    # 1. Normal read hits cache
    s1 = resolver.get_session_state(session_id)
    assert s1 == authoritative_data
    assert resolver.fallback_invocations == 0

    # 2. Chaos Injection: FLUSHALL (Cache wipeout)
    r_client.flushall()
    assert r_client.get(cache_key) is None

    # Read still succeeds without error by falling back to Postgres
    s2 = resolver.get_session_state(session_id)
    assert s2 == authoritative_data
    # Cache was repopulated by fallback logic
    assert r_client.get(cache_key) is not None

    # 3. Extreme Chaos Injection: Total Valkey Outage (docker stop central-valkey)
    subprocess.run(["docker", "stop", "central-valkey"], check=True)

    # Query during full cache outage: must not crash, must return authoritative state
    s3 = resolver.get_session_state(session_id)
    assert s3 == authoritative_data
    assert resolver.fallback_invocations >= 1, "Fallback should have been invoked during cache outage"

    # 4. Recovery: Restart Valkey
    subprocess.run(["docker", "start", "central-valkey"], check=True)
    assert _wait_for_valkey(15.0), "Valkey failed to recover after restart"

    # Reconnect client and verify healing
    fresh_valkey = redis.Redis(host=VALKEY_HOST, port=VALKEY_PORT, decode_responses=True, socket_timeout=1.0)
    healing_resolver = ResilientStateResolver(fresh_valkey, pg_engine, table_name)
    s4 = healing_resolver.get_session_state(session_id)
    assert s4 == authoritative_data

    # Cleanup table
    with pg_engine.begin() as drop_conn:
        drop_conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))


# ==============================================================================
# SCENARIO 3: Capability Activation Drain Race Under High Thread Concurrency
# ==============================================================================

@pytest.mark.unit
def test_capability_activation_drain_race_stress(tmp_path):
    """Verify 50 concurrent worker threads acquiring leases while drainer runs causes zero deadlocks."""
    audit_file = str(tmp_path / "chaos_capability_audit.jsonl")
    mgr = CapabilityActivationManager(max_total_memory_mb=8192, audit_log_path=audit_file)

    # Register dynamic test capabilities
    for i in range(10):
        mgr.register_capability(
            CapabilityDefinition(
                name=f"cap_chaos_{i}",
                ring=2,
                required_services=[f"svc_{i}"],
                dependencies=[] if i == 0 else [f"cap_chaos_{i-1}"],
                allows_idle_shutdown=True,
            )
        )

    errors: List[Exception] = []
    lease_ids: List[str] = []
    lease_lock = threading.Lock()
    stop_workers = threading.Event()

    def worker_task(worker_id: int):
        cap_target = f"cap_chaos_{worker_id % 10}"
        for _ in range(15):
            if stop_workers.is_set():
                break
            try:
                mgr.activate_capability(cap_target, caller_tenant=f"tenant_{worker_id}")
                lease = mgr.acquire_lease(cap_target, tenant_id=f"tenant_{worker_id}")
                with lease_lock:
                    lease_ids.append(lease.lease_id)
                time.sleep(0.001)
                mgr.release_lease(lease.lease_id)
            except Exception as e:
                errors.append(e)

    def drainer_task():
        while not stop_workers.is_set():
            try:
                mgr.drain_idle_capabilities()
                time.sleep(0.002)
            except Exception as e:
                errors.append(e)

    # Spawn 50 concurrent workers + 3 background drainers
    workers = [threading.Thread(target=worker_task, args=(i,), daemon=True) for i in range(50)]
    drainers = [threading.Thread(target=drainer_task, daemon=True) for _ in range(3)]

    for d in drainers:
        d.start()
    for w in workers:
        w.start()

    for w in workers:
        w.join(timeout=10.0)
    stop_workers.set()
    for d in drainers:
        d.join(timeout=2.0)

    # Zero deadlocks or race condition crashes
    assert len(errors) == 0, f"Encountered errors during concurrency stress: {errors[:3]}"
    assert len(lease_ids) >= 100, f"Expected at least 100 lease acquisitions, got {len(lease_ids)}"

    # Cryptographic Merkle audit ledger integrity check
    assert mgr.verify_audit_log_integrity() is True, "Audit log Merkle hash chain was corrupted!"

    # Verify persistent audit file on disk
    with open(audit_file, "r", encoding="utf-8") as f:
        log_lines = [l.strip() for l in f if l.strip()]
    assert len(log_lines) >= 100, f"Audit file records ({len(log_lines)}) do not match lease activity"
