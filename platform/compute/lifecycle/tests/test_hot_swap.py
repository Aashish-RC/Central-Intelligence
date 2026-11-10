"""Unit tests for ModelHotSwapManager (Task 16.5)."""

import concurrent.futures
import time
import pytest
from platform.compute.lifecycle.hot_swap import (
    ModelHotSwapManager,
)


@pytest.fixture
def manager():
    return ModelHotSwapManager(initial_model="claude-3-7-sonnet")


def test_swap_claude_to_gpt4_zero_dropped_requests(manager: ModelHotSwapManager):
    """Acceptance test: Swap Claude -> GPT-4 with zero dropped requests."""
    assert manager.active_model == "claude-3-7-sonnet"

    # Start in-flight requests on Claude
    handle_1 = manager.acquire("req_101")
    handle_2 = manager.acquire("req_102")

    assert handle_1.model_id == "claude-3-7-sonnet"
    assert handle_2.model_id == "claude-3-7-sonnet"
    assert manager.get_in_flight_count("claude-3-7-sonnet") == 2

    # Perform hot swap to GPT-4
    swap_event = manager.hot_swap("gpt-4o")
    assert swap_event.from_model == "claude-3-7-sonnet"
    assert swap_event.to_model == "gpt-4o"
    assert swap_event.in_flight_during_swap == 2
    assert manager.active_model == "gpt-4o"

    # New request arrives after hot swap -> automatically routes to GPT-4
    handle_3 = manager.acquire("req_103")
    assert handle_3.model_id == "gpt-4o"

    # Previous in-flight requests on Claude finish gracefully
    manager.release(handle_1)
    assert manager.get_in_flight_count("claude-3-7-sonnet") == 1

    manager.release(handle_2)
    assert manager.get_in_flight_count("claude-3-7-sonnet") == 0

    # Clean up handle_3
    manager.release(handle_3)
    assert manager.get_in_flight_count() == 0


def test_concurrent_hot_swap_execution(manager: ModelHotSwapManager):
    """Under multi-threaded concurrent load, all requests finish without drops."""
    total_requests = 60
    results = []

    def run_worker(req_id: int):
        def executor(model_id: str):
            time.sleep(0.01)
            return (req_id, model_id)

        return manager.execute(f"req_{req_id}", executor)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = []
        for i in range(total_requests):
            futures.append(pool.submit(run_worker, i))
            if i == 25:
                # Trigger hot-swap mid-stream
                manager.hot_swap("gpt-4o")

        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    assert len(results) == total_requests
    claude_serviced = sum(1 for _, m in results if m == "claude-3-7-sonnet")
    gpt4_serviced = sum(1 for _, m in results if m == "gpt-4o")

    # Both models serviced requests during transition and total is intact
    assert claude_serviced > 0
    assert gpt4_serviced > 0
    assert claude_serviced + gpt4_serviced == total_requests
    assert manager.get_in_flight_count() == 0

