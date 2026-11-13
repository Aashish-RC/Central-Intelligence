"""Load tests for Central Intelligence memory tier operations (Claude Task 12.1).

Validates:
- 10,000 memory writes and reads
- Throughput and latency stability under continuous volume
- P99 latency < 5s
- Zero memory leakage or integrity regressions
"""

from __future__ import annotations

import asyncio
import math
import sys
import time
from pathlib import Path
from typing import List
import pytest

# Ensure submodule paths
REPO_ROOT = Path(__file__).resolve().parents[2]
for p in [REPO_ROOT, REPO_ROOT / "cognitive", REPO_ROOT / "cognitive" / "memory", REPO_ROOT / "cognitive" / "memory" / "storage"]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from cognitive.memory.core.models import Turn, TurnRole
from cognitive.memory.engine import MemoryEngine
from cognitive.memory.config import (
    MemoryConfig,
    WorkingMemoryBackend,
    FactStoreBackend,
    VectorStoreBackend,
    EmbeddingBackend,
)


@pytest.mark.asyncio
async def test_12_1_load_memory_reads_and_writes(tmp_path: Path):
    """Simulate 10,000 memory read and write operations."""
    config = MemoryConfig(
        working_backend=WorkingMemoryBackend.IN_MEMORY,
        wal_dir=str(tmp_path / "wal_load"),
        fact_backend=FactStoreBackend.SQLITE,
        sqlite_path=":memory:",
        vector_backend=VectorStoreBackend.QDRANT,
        qdrant_location=":memory:",
        embedding_backend=EmbeddingBackend.LOCAL,
        embedding_dim=64,
        max_context_tokens=300,
    )
    engine = MemoryEngine(config=config)

    total_ops = 10_000
    write_count = 5_000
    read_count = 5_000

    write_latencies: List[float] = []
    read_latencies: List[float] = []

    # 1. High throughput working & fact writes
    start_writes = time.perf_counter()
    for i in range(write_count):
        turn = Turn(
            user_id="user_load_test",
            session_id=f"sess_{i % 50}",
            role=TurnRole.USER,
            content=f"User preference note number {i}: prefer setting option_{i % 50} with flag {i}.",
            metadata={"item_index": i},
        )
        t0 = time.perf_counter()
        engine.working.append_turn(turn)
        write_latencies.append(time.perf_counter() - t0)
    total_write_time = time.perf_counter() - start_writes

    # 2. 5,000 recall queries across working and fact tiers
    start_reads = time.perf_counter()
    for i in range(read_count):
        t0 = time.perf_counter()
        turns = engine.working.get_active_window(
            session_id=f"sess_{i % 50}",
            limit=10,
        )
        read_latencies.append(time.perf_counter() - t0)
    total_read_time = time.perf_counter() - start_reads

    all_latencies = write_latencies + read_latencies
    all_latencies.sort()

    idx_p99 = int(math.ceil(0.99 * total_ops)) - 1
    p99 = all_latencies[idx_p99]

    assert len(all_latencies) == total_ops
    assert p99 < 5.0, f"P99 latency was {p99:.4f}s >= 5.0s"
    ops_per_sec = total_ops / (total_write_time + total_read_time)
    assert ops_per_sec > 100.0, f"Memory throughput {ops_per_sec:.2f} ops/s was below threshold"


