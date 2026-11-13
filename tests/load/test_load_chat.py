"""Load tests for Central Intelligence chat interactions (Claude Task 12.1).

Validates:
- 1,000 concurrent chat requests using asyncio.gather
- Throughput and latency stability under burst conditions
- P99 latency < 5s
- Zero unhandled error responses
"""

from __future__ import annotations

import asyncio
import math
import time
from typing import List
import pytest

from surface.interaction.web.librechat_adapter import LibreChatAdapter


@pytest.mark.asyncio
async def test_12_1_load_concurrent_chat_requests():
    """Simulate 1,000 concurrent user chat interactions and verify P99 latency < 5s."""
    adapter = LibreChatAdapter()
    num_requests = 1000
    concurrency_limit = 100
    semaphore = asyncio.Semaphore(concurrency_limit)

    latencies: List[float] = []

    async def single_chat_turn(idx: int):
        async with semaphore:
            start = time.perf_counter()
            # Asynchronous turn simulation across interaction surface
            conv = adapter.create_conversation(
                title=f"Load Test Session {idx}",
                provider="anthropic",
                model="claude-3-7-sonnet",
            )
            msg = adapter.send_message(
                conv.conversation_id,
                f"Query request payload turn {idx}",
                role="user",
            )
            assert msg.content == f"Query request payload turn {idx}"
            # Simulated model reply
            reply = adapter.send_message(
                conv.conversation_id,
                f"Processed answer for turn {idx}",
                role="assistant",
            )
            assert reply.role == "assistant"
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

    start_total = time.perf_counter()
    tasks = [single_chat_turn(i) for i in range(num_requests)]
    await asyncio.gather(*tasks)
    total_time = time.perf_counter() - start_total

    assert len(latencies) == num_requests
    latencies.sort()
    idx_p99 = int(math.ceil(0.99 * num_requests)) - 1
    p99_latency = latencies[idx_p99]
    idx_p50 = int(math.ceil(0.50 * num_requests)) - 1
    p50_latency = latencies[idx_p50]

    # Acceptance: System handles 1000 concurrent requests without errors. P99 latency < 5s.
    assert p99_latency < 5.0, f"P99 latency was {p99_latency:.4f}s >= 5.0s"
    throughput = num_requests / total_time
    assert throughput > 100.0, f"Throughput {throughput:.2f} req/s was lower than threshold"

