"""Test Suite for SigNoz OpenTelemetry Observability Adapter.
(Layer 14: Features 14.01–14.12)
"""

import time
import pytest
from control.observability.models import TraceStatus
from control.observability.signoz import SigNozAdapter


@pytest.fixture
def signoz():
    return SigNozAdapter()


def test_1_distributed_trace_across_layers(signoz):
    """Test 1: Trace spans across L1 -> L2 -> L3 -> L4 -> L5 linked to same trace_id (14.09)."""
    # L1: Perception root
    root = signoz.start_trace("user_query_inbound", layer="L1", attributes={"query": "Calculate revenue"})
    time.sleep(0.01)

    # L2: Memory lookup child
    l2_span = signoz.create_child_span(root, "memory_recall", layer="L2")
    time.sleep(0.01)
    l2_span.finish()

    # L3: Knowledge search child
    l3_span = signoz.create_child_span(root, "hybrid_search", layer="L3")
    time.sleep(0.01)
    l3_span.finish()

    # L4: Model inference child
    l4_span = signoz.create_child_span(root, "llm_generate", layer="L4")
    time.sleep(0.02)
    l4_span.finish()

    # L5: Action execution child
    l5_span = signoz.create_child_span(root, "tool_execution", layer="L5")
    time.sleep(0.01)
    l5_span.finish()

    root.finish()

    trace_spans = signoz.get_trace(root.trace_id)
    assert len(trace_spans) == 5
    layers = {s.layer for s in trace_spans}
    assert layers == {"L1", "L2", "L3", "L4", "L5"}
    assert all(s.trace_id == root.trace_id for s in trace_spans)
    assert root.duration_ms > 0


def test_2_latency_percentiles_calculation(signoz):
    """Test 2: Latency percentiles (P50, P90, P95, P99) calculation (14.02)."""
    # Simulate 100 operations with varied latencies
    for i in range(1, 101):
        span = signoz.start_trace("db_query", layer="L2")
        span.start_time = 1000.0
        span.end_time = 1000.0 + (i / 1000.0)  # 1ms to 100ms
        span.finish()

    percentiles = signoz.get_latency_percentiles("db_query")
    assert percentiles.sample_count == 100
    assert 45.0 <= percentiles.p50_ms <= 55.0
    assert 85.0 <= percentiles.p90_ms <= 95.0
    assert 95.0 <= percentiles.p99_ms <= 100.0
    assert percentiles.min_ms == pytest.approx(1.0, abs=1e-3)
    assert percentiles.max_ms == pytest.approx(100.0, abs=1e-3)


def test_3_token_usage_and_cost_attribution(signoz):
    """Test 3: Token usage and real-time cost attribution (14.01, 14.07)."""
    signoz.record_token_usage(
        user_id="user_alice",
        tenant_id="tenant_acme",
        model="gpt-4o",
        prompt_tokens=500,
        completion_tokens=200,
        cost_usd=0.0125,
    )

    metrics = [m for m in signoz._metrics if m.labels.get("user_id") == "user_alice"]
    assert len(metrics) == 4
    names = {m.name for m in metrics}
    assert "llm.tokens.prompt" in names
    assert "llm.tokens.completion" in names
    assert "llm.tokens.total" in names
    assert "llm.cost.usd" in names


def test_4_cache_hit_rate(signoz):
    """Test 4: Cache hit rate calculation (14.06)."""
    signoz.record_cache_access(hit=True)
    signoz.record_cache_access(hit=True)
    signoz.record_cache_access(hit=True)
    signoz.record_cache_access(hit=False)

    rate = signoz.get_cache_hit_rate()
    assert rate == 0.75


def test_5_error_rate_and_request_replay(signoz):
    """Test 5: Error rate tracking and request replay metadata (14.03, 14.12)."""
    root_ok = signoz.start_trace("chat", layer="L4", attributes={"prompt": "Hello"})
    root_ok.finish(TraceStatus.OK)

    root_err = signoz.start_trace("chat", layer="L4", attributes={"prompt": "Cause error"})
    root_err.finish(TraceStatus.ERROR)

    err_rate = signoz.get_error_rate()
    assert err_rate == 0.50

    replay = signoz.replay_request_metadata(root_ok.trace_id)
    assert replay is not None
    assert replay["trace_id"] == root_ok.trace_id
    assert replay["attributes"]["prompt"] == "Hello"
