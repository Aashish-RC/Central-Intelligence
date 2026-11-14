"""SigNoz OpenTelemetry Observability Adapter (Layer 14: Features 14.01–14.12).

Provides distributed tracing, telemetry metric counters, latency distribution percentiles,
and cross-layer trace visualization backed by OpenTelemetry standard semantics.
"""

from __future__ import annotations

import logging
import math
import os
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from control.observability.models import (
    MetricRecord,
    PercentileMetrics,
    SpanRecord,
    TraceStatus,
)
from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    require_live_adapter,
)

logger = logging.getLogger("control.observability.signoz")


class SigNozAdapter:
    """OpenTelemetry-native observability engine connecting to SigNoz collectors."""

    def __init__(
        self,
        endpoint_url: str = "http://localhost:4318",
        service_name: str = "central-intelligence",
        _defer_prod_check: bool = False,
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.service_name = service_name
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("signoz")
        )

        # Local in-memory repository for trace inspection and hermetic tests
        self._spans: List[SpanRecord] = []
        self._metrics: List[MetricRecord] = []
        self._cache_stats = {"hits": 0, "misses": 0}
        self._queue_depth: int = 0

        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            try:
                from opentelemetry import trace
                from opentelemetry.sdk.resources import Resource
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                resource = Resource.create({"service.name": self.service_name})
                provider = TracerProvider(resource=resource)
                exporter = OTLPSpanExporter(
                    endpoint=f"{self.endpoint_url}/v1/traces",
                )
                processor = BatchSpanProcessor(exporter)
                provider.add_span_processor(processor)
                trace.set_tracer_provider(provider)
                self._tracer = trace.get_tracer(self.service_name)
                self._otel_enabled = True
            except ImportError:
                fail_closed_in_production(
                    "signoz",
                    "opentelemetry-sdk not installed; pip install -e '.[observability]' required for live mode",
                )
            except Exception as exc:
                fail_closed_in_production("signoz", f"OTLP exporter init failed: {exc}", cause=exc)
        else:
            self._tracer = None
            self._otel_enabled = False

        if not _defer_prod_check and self.adapter_mode == "live":
            self._ensure_live_backend()

    def _ensure_live_backend(self) -> None:
        """Verify live SigNoz / OTLP endpoint in live mode."""
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            return
        try:
            with httpx.Client(timeout=2.0) as client:
                client.get(self.endpoint_url)
        except ProductionSafetyError:
            raise
        except Exception as exc:
            fail_closed_in_production(
                "signoz",
                f"SigNoz / OTLP collector at {self.endpoint_url} is unreachable: {exc}",
                cause=exc,
            )

    def start_trace(
        self,
        name: str,
        layer: str = "L4",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> SpanRecord:
        """Starts a root span for a distributed request execution (14.09)."""
        self._ensure_live_backend()
        trace_id = str(uuid4())
        span = SpanRecord(
            trace_id=trace_id,
            parent_span_id=None,
            name=name,
            layer=layer,
            attributes=attributes or {},
        )
        if self._otel_enabled and self._tracer is not None:
            try:
                span_ctx = self._tracer.start_span(name, attributes=attributes or {})
                span.otel_span = span_ctx
                span.otel_span.set_attribute("ci.layer", layer)
                from opentelemetry.trace import format_trace_id, format_span_id
                otel_ctx = span.otel_span.get_span_context()
                span.trace_id = format_trace_id(otel_ctx.trace_id)
                span.span_id = format_span_id(otel_ctx.span_id)
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production("signoz", f"Failed to start span in OTel: {exc}", cause=exc)

        self._spans.append(span)
        return span

    def create_child_span(
        self,
        parent_span: SpanRecord,
        name: str,
        layer: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> SpanRecord:
        """Spawns an asynchronous child span linked to the parent trace."""
        self._ensure_live_backend()
        span = SpanRecord(
            trace_id=parent_span.trace_id,
            parent_span_id=parent_span.span_id,
            name=name,
            layer=layer,
            attributes=attributes or {},
        )
        if self._otel_enabled and self._tracer is not None and getattr(parent_span, "otel_span", None) is not None:
            try:
                from opentelemetry import trace
                from opentelemetry.trace import format_span_id
                ctx = trace.set_span_in_context(parent_span.otel_span)
                child_otel = self._tracer.start_span(name, context=ctx, attributes=attributes or {})
                child_otel.set_attribute("ci.layer", layer)
                span.otel_span = child_otel
                span.span_id = format_span_id(child_otel.get_span_context().span_id)
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production("signoz", f"Failed to create child span in OTel: {exc}", cause=exc)

        self._spans.append(span)
        return span

    def record_metric(
        self,
        name: str,
        value: float,
        metric_type: str = "gauge",
        unit: str = "count",
        labels: Optional[Dict[str, str]] = None,
    ) -> MetricRecord:
        """Records a time-series telemetry metric."""
        metric = MetricRecord(
            name=name,
            value=value,
            metric_type=metric_type,
            unit=unit,
            labels=labels or {},
        )
        self._metrics.append(metric)
        return metric

    def record_token_usage(
        self,
        user_id: str,
        tenant_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float = 0.0,
    ) -> None:
        """Records token metrics and real-time cost attribution (14.01, 14.07)."""
        labels = {"user_id": user_id, "tenant_id": tenant_id, "model": model}
        self.record_metric("llm.tokens.prompt", float(prompt_tokens), "counter", "tokens", labels)
        self.record_metric("llm.tokens.completion", float(completion_tokens), "counter", "tokens", labels)
        self.record_metric("llm.tokens.total", float(prompt_tokens + completion_tokens), "counter", "tokens", labels)
        if cost_usd > 0.0:
            self.record_metric("llm.cost.usd", cost_usd, "counter", "usd", labels)

    def record_cache_access(self, hit: bool) -> None:
        """Tracks semantic / model cache hit rates (14.06)."""
        if hit:
            self._cache_stats["hits"] += 1
            self.record_metric("cache.hits", 1.0, "counter")
        else:
            self._cache_stats["misses"] += 1
            self.record_metric("cache.misses", 1.0, "counter")

    def get_cache_hit_rate(self) -> float:
        total = self._cache_stats["hits"] + self._cache_stats["misses"]
        return (self._cache_stats["hits"] / total) if total > 0 else 0.0

    def set_queue_depth(self, depth: int) -> None:
        """Tracks async job and message queue depth (14.05)."""
        self._queue_depth = depth
        self.record_metric("queue.depth", float(depth), "gauge", "items")

    def get_latency_percentiles(self, operation: Optional[str] = None) -> PercentileMetrics:
        """Computes P50, P90, P95, and P99 latency percentiles over completed spans (14.02)."""
        durations = [
            s.duration_ms for s in self._spans
            if s.end_time is not None and (operation is None or s.name == operation)
        ]

        if not durations:
            return PercentileMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)

        durations.sort()
        n = len(durations)

        def percentile(p: float) -> float:
            idx = int(math.ceil(p * n)) - 1
            return durations[max(0, min(idx, n - 1))]

        return PercentileMetrics(
            p50_ms=percentile(0.50),
            p90_ms=percentile(0.90),
            p95_ms=percentile(0.95),
            p99_ms=percentile(0.99),
            min_ms=durations[0],
            max_ms=durations[-1],
            sample_count=n,
        )

    def get_error_rate(self, since: Optional[float] = None) -> float:
        """Computes system error rate (14.03)."""
        completed = [
            s for s in self._spans
            if s.end_time is not None and (since is None or s.start_time >= since)
        ]
        if not completed:
            return 0.0

        errors = sum(1 for s in completed if s.status == TraceStatus.ERROR)
        return errors / len(completed)

    def get_trace(self, trace_id: str) -> List[SpanRecord]:
        """Returns all spans belonging to a distributed request trace (14.09)."""
        return [s for s in self._spans if s.trace_id == trace_id]

    def replay_request_metadata(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves exact metadata and context inputs for request replay & debugging (14.12)."""
        spans = self.get_trace(trace_id)
        if not spans:
            return None

        root = next((s for s in spans if s.parent_span_id is None), spans[0])
        return {
            "trace_id": trace_id,
            "root_operation": root.name,
            "start_time": root.start_time,
            "total_spans": len(spans),
            "layers_involved": list(set(s.layer for s in spans)),
            "attributes": root.attributes,
        }

