"""OpenMeter Real-Time Token Metering Adapter (Layer 13: Features 13.09, 13.10).

Ingests CloudEvents for every token consumed (prompt, completion, cached) across models,
aggregating per user, tenant, and application with real-time cost attribution.
Supports live HTTP dispatch to OpenMeter instances and local in-memory aggregation fallback.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from control.billing.models import MeteredUsageSummary, TokenUsageEvent

logger = logging.getLogger("control.billing.metering")


class OpenMeterAdapter:
    """Enterprise token metering adapter supporting OpenMeter CloudEvents specification."""

    def __init__(
        self,
        endpoint_url: str = "http://localhost:8888",
        api_token: Optional[str] = None,
        source: str = "central-intelligence/reasoning",
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.api_token = api_token
        self.source = source
        self._local_events: List[TokenUsageEvent] = []

    def record_event(
        self,
        event: TokenUsageEvent,
        dispatch_remote: bool = True,
    ) -> Dict[str, Any]:
        """Ingests a token consumption event, converting to CloudEvents 1.0 schema."""
        # Always maintain local telemetry buffer
        self._local_events.append(event)

        cloud_event = {
            "specversion": "1.0",
            "id": event.event_id,
            "source": self.source,
            "type": "token_consumption",
            "subject": f"user:{event.user_id}",
            "time": datetime.fromtimestamp(event.timestamp, tz=timezone.utc).isoformat(),
            "data": {
                "user_id": event.user_id,
                "tenant_id": event.tenant_id,
                "app_id": event.app_id,
                "model": event.model,
                "prompt_tokens": event.prompt_tokens,
                "completion_tokens": event.completion_tokens,
                "cached_tokens": event.cached_tokens,
                "total_tokens": event.total_tokens,
                "cost_usd": event.cost_usd,
                "byok": event.byok,
                "billable": event.billable,
                "compute_provider": event.compute_provider,
                **(event.metadata or {}),
            },
        }

        remote_success = False
        if dispatch_remote:
            try:
                headers = {"Content-Type": "application/cloudevents+json"}
                if self.api_token:
                    headers["Authorization"] = f"Bearer {self.api_token}"

                with httpx.Client(timeout=1.0) as client:
                    resp = client.post(
                        f"{self.endpoint_url}/api/v1/events",
                        json=cloud_event,
                        headers=headers,
                    )
                    remote_success = resp.status_code in (200, 201, 202)
            except Exception as e:
                logger.debug("OpenMeter remote dispatch failed, retained in local buffer: %s", e)
                remote_success = False

        return {
            "event_id": event.event_id,
            "cloud_event": cloud_event,
            "remote_dispatched": remote_success,
            "stored_locally": True,
        }

    def query_usage(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        app_id: Optional[str] = None,
        since: Optional[float] = None,
    ) -> MeteredUsageSummary:
        """Aggregates metered usage across criteria."""
        filtered = self._local_events
        if user_id:
            filtered = [e for e in filtered if e.user_id == user_id]
        if tenant_id:
            filtered = [e for e in filtered if e.tenant_id == tenant_id]
        if app_id:
            filtered = [e for e in filtered if e.app_id == app_id]
        if since is not None:
            filtered = [e for e in filtered if e.timestamp >= since]

        summary = MeteredUsageSummary(
            user_id=user_id or "all",
            tenant_id=tenant_id or "all",
            app_id=app_id,
            events_count=len(filtered),
        )

        for ev in filtered:
            summary.total_tokens += ev.total_tokens
            summary.total_cost_usd += ev.cost_usd

            if ev.byok:
                summary.byok_tokens += ev.total_tokens
            if ev.billable and not ev.byok:
                summary.billable_tokens += ev.total_tokens
                summary.billable_cost_usd += ev.cost_usd

            summary.by_model[ev.model] = summary.by_model.get(ev.model, 0) + ev.total_tokens

        return summary

    def get_breakdown_by_app(self, tenant_id: str) -> Dict[str, MeteredUsageSummary]:
        """Provides per-app cost and token usage breakdown for tenant chargebacks."""
        apps: Dict[str, List[TokenUsageEvent]] = {}
        for ev in self._local_events:
            if ev.tenant_id == tenant_id:
                apps.setdefault(ev.app_id, []).append(ev)

        result: Dict[str, MeteredUsageSummary] = {}
        for app_name, events in apps.items():
            s = MeteredUsageSummary(user_id="all", tenant_id=tenant_id, app_id=app_name)
            for ev in events:
                s.total_tokens += ev.total_tokens
                s.total_cost_usd += ev.cost_usd
                if ev.billable and not ev.byok:
                    s.billable_tokens += ev.total_tokens
                    s.billable_cost_usd += ev.cost_usd
                s.events_count += 1
            result[app_name] = s

        return result

