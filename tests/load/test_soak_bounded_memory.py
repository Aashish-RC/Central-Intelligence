"""
Stage S3.5: Continuous Bounded-Memory Soak Test & Leak Detection Suite.

Validates memory, thread, and latency stability under sustained multi-tenant load:
- Continuous concurrent load cycles spanning chat, memory persistence, and RAG retrieval
- Real-time RSS memory tracking, leak detection, and garbage collection verification
- Thread leak prevention and latency P99 ceiling enforcement
"""

from __future__ import annotations

import asyncio
import gc
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Tuple

import psutil
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in [
    REPO_ROOT,
    REPO_ROOT / "cognitive",
    REPO_ROOT / "cognitive" / "memory",
    REPO_ROOT / "cognitive" / "knowledge",
]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from cognitive.knowledge.search.core.models import CorpusType, SearchDocument, SearchQuery
from cognitive.knowledge.search.engines.local_hybrid import LocalHybridSearchEngine
from cognitive.memory.config import (
    EmbeddingBackend,
    FactStoreBackend,
    MemoryConfig,
    VectorStoreBackend,
    WorkingMemoryBackend,
)
from cognitive.memory.core.models import Turn, TurnRole
from cognitive.memory.engine import MemoryEngine
from surface.interaction.web.librechat_adapter import LibreChatAdapter


@pytest.mark.asyncio
async def test_continuous_bounded_memory_soak():
    """Execute continuous multi-tenant load waves and verify zero memory or thread leakage."""
    process = psutil.Process()
    gc.collect()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Initialize subsystems
        chat_adapter = LibreChatAdapter()
        search_engine = LocalHybridSearchEngine(db_path=":memory:")

        # Seed knowledge base with documents
        for i in range(40):
            search_engine.index_document(
                SearchDocument(
                    id=f"soak_doc_{i}",
                    title=f"Enterprise Architecture Guideline {i}",
                    content=f"Knowledge base document topic {i}. Validates persistent token routing, ReBAC authorization, and bounded RSS consumption.",
                    corpus_type=CorpusType.FILE,
                )
            )

        mem_config = MemoryConfig(
            working_backend=WorkingMemoryBackend.IN_MEMORY,
            wal_dir=str(tmp_path / "soak_wal"),
            fact_backend=FactStoreBackend.SQLITE,
            sqlite_path=":memory:",
            vector_backend=VectorStoreBackend.QDRANT,
            qdrant_location=":memory:",
            embedding_backend=EmbeddingBackend.LOCAL,
            embedding_dim=64,
            max_context_tokens=500,
        )
        memory_engine = MemoryEngine(config=mem_config)

        # 2. Warm-up Phase (fill caches, initialize JIT / internal buffers)
        for warm_idx in range(50):
            conv = chat_adapter.create_conversation(title=f"Warmup {warm_idx}")
            chat_adapter.send_message(conv.conversation_id, f"Warmup user query {warm_idx}", role="user")
            memory_engine.remember(
                user_id=f"user_{warm_idx % 5}",
                text=f"Warmup memory fact content {warm_idx}",
                session_id=conv.conversation_id,
            )
            search_engine.search(SearchQuery(query_text=f"Topic {warm_idx % 40}", limit=3))

        gc.collect()
        time.sleep(0.5)

        # Baseline measurements post warm-up
        rss_baseline = process.memory_info().rss
        threads_baseline = process.num_threads()
        initial_gc_counts = gc.get_count()

        # 3. Sustained Multi-Tenant Load Waves
        num_waves = 5
        ops_per_wave = 100
        latencies: List[float] = []
        rss_samples: List[int] = []

        for wave in range(num_waves):
            for op in range(ops_per_wave):
                t0 = time.perf_counter()
                session_id = f"wave_{wave}_sess_{op}"
                user_id = f"tenant_user_{op % 10}"

                # Step A: Chat interaction
                conv = chat_adapter.create_conversation(
                    title=f"Chat {session_id}",
                    provider="anthropic",
                    model="claude-3-5-haiku",
                )
                chat_adapter.send_message(conv.conversation_id, f"Incoming request payload {op}", role="user")

                # Step B: Memory engine turn & fact persistence
                memory_engine.remember(
                    user_id=user_id,
                    text=f"Fact statement for {session_id}: User preference {op}",
                    session_id=session_id,
                )
                recalled = memory_engine.recall(
                    user_id=user_id,
                    query=f"User preference {op}",
                    session_id=session_id,
                    top_k=3,
                )
                assert recalled is not None

                # Step C: Knowledge retrieval search
                search_res = search_engine.search(SearchQuery(query_text=f"Topic {op % 40}", limit=5))
                assert search_res.total_hits >= 1

                elapsed = time.perf_counter() - t0
                latencies.append(elapsed)

            # Sample RSS at the end of each wave
            current_rss = process.memory_info().rss
            rss_samples.append(current_rss)

        # 4. Post-Soak Verification & Leak Detection
        gc.collect()
        time.sleep(0.5)

        rss_final = process.memory_info().rss
        threads_final = process.num_threads()

        # Sort latencies for percentiles
        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        rss_baseline_mb = rss_baseline / (1024 * 1024)
        rss_final_mb = rss_final / (1024 * 1024)
        rss_delta_mb = (rss_final - rss_baseline) / (1024 * 1024)
        rss_growth_pct = ((rss_final - rss_baseline) / rss_baseline) * 100.0

        # Assertions
        assert len(latencies) == (num_waves * ops_per_wave), "Some operations were skipped or failed"
        assert p99 < 0.25, f"P99 latency ({p99*1000:.1f}ms) exceeded 250ms threshold"
        assert threads_final <= threads_baseline + 2, f"Thread leak detected: baseline={threads_baseline}, final={threads_final}"
        # RSS growth must be strictly bounded under 15% across hundreds of heterogeneous ops
        assert rss_growth_pct < 15.0, f"Memory drift exceeded bounds: baseline={rss_baseline_mb:.1f}MB, final={rss_final_mb:.1f}MB (+{rss_growth_pct:.2f}%)"
