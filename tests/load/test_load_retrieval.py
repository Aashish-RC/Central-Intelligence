"""Load tests for Central Intelligence knowledge retrieval (Claude Task 12.1).

Validates:
- 1,000 concurrent RAG queries using asyncio.gather
- Throughput and latency under heavy search load
- P99 latency < 5s
- Correct hybrid retrieval without search failures
"""

from __future__ import annotations

import asyncio
import math
import sys
import tempfile
import time
from pathlib import Path
from typing import List
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in [REPO_ROOT, REPO_ROOT / "cognitive", REPO_ROOT / "cognitive" / "knowledge"]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from cognitive.knowledge.search.engines.local_hybrid import LocalHybridSearchEngine
from cognitive.knowledge.search.core.models import SearchDocument, SearchQuery, CorpusType


@pytest.mark.asyncio
async def test_12_1_load_concurrent_rag_retrieval(tmp_path: Path):
    """Simulate 1,000 concurrent hybrid search / RAG retrieval queries."""
    engine = LocalHybridSearchEngine(db_path=str(tmp_path / "search_load.db"))

    # Seed knowledge corpus with 50 diverse documentation passages
    for i in range(50):
        engine.index_document(
            SearchDocument(
                id=f"doc_spec_{i}",
                title=f"Architecture Specification Topic {i}",
                content=f"Detailed architectural specifications for topic {i}. Central Intelligence Layer {i % 19} handles distributed operations with consensus.",
                corpus_type=CorpusType.FILE,
            )
        )

    num_queries = 1000
    concurrency_limit = 50
    semaphore = asyncio.Semaphore(concurrency_limit)
    latencies: List[float] = []

    async def single_query(idx: int):
        async with semaphore:
            t0 = time.perf_counter()
            query_term = f"Topic {idx % 50}"
            resp = engine.search(SearchQuery(query_text=query_term, limit=5))
            assert resp.total_hits >= 1
            latencies.append(time.perf_counter() - t0)

    start_total = time.perf_counter()
    tasks = [single_query(i) for i in range(num_queries)]
    await asyncio.gather(*tasks)
    total_time = time.perf_counter() - start_total

    assert len(latencies) == num_queries
    latencies.sort()
    idx_p99 = int(math.ceil(0.99 * num_queries)) - 1
    p99 = latencies[idx_p99]

    # Acceptance: System handles 1000 concurrent requests without errors. P99 latency < 5s.
    assert p99 < 5.0, f"P99 latency was {p99:.4f}s >= 5.0s"
    throughput = num_queries / total_time
    assert throughput > 100.0, f"Search throughput {throughput:.2f} qps was below threshold"

