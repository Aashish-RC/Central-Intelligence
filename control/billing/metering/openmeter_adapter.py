"""OpenMeter Real-Time Token Metering Adapter (Layer 13: Features 13.09, 13.10).

Ingests CloudEvents for every token consumed (prompt, completion, cached) across models,
aggregating per user, tenant, and application with real-time cost attribution.
Supports live HTTP dispatch to OpenMeter instances and local in-memory aggregation fallback.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from control.billing.models import MeteredUsageSummary, TokenUsageEvent
from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    require_live_adapter,
)

logger = logging.getLogger("control.billing.metering")


class OpenMeterAdapter:
    """Enterprise token metering adapter supporting OpenMeter CloudEvents specification."""

    def __init__(
        self,
        endpoint_url: str = "http://localhost:8888",
        api_token: Optional[str] = None,
        source: str = "central-intelligence/reasoning",
        _defer_prod_check: bool = False,
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.api_token = api_token
        self.source = source
        self._local_events: List[TokenUsageEvent] = []
        self._client: Optional[httpx.Client] = None
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("openmeter")
        )

    def _http_client(self) -> httpx.Client:
        """Cached httpx.Client bound to endpoint_url with 5-second timeout."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self.endpoint_url,
                timeout=5.0,
            )
        return self._client

    def _auth_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

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
                headers.update(self._auth_headers())

                resp = self._http_client().post(
                    "/api/v1/events",
                    json=cloud_event,
                    headers=headers,
                    timeout=1.0,
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

    def _build_summary_from_openmeter_response(
        self,
        data: Any,
        user_id: Optional[str],
        tenant_id: Optional[str],
        app_id: Optional[str],
    ) -> MeteredUsageSummary:
        summary = MeteredUsageSummary(
            user_id=user_id or "all",
            tenant_id=tenant_id or "all",
            app_id=app_id,
        )
        rows: List[Any] = []
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                rows = data["data"]
            else:
                rows = [data]
        elif isinstance(data, list):
            rows = data

        for row in rows:
            if not isinstance(row, dict):
                continue
            val = int(row.get("value", 0))
            summary.total_tokens += val
            summary.billable_tokens += val
            summary.events_count += 1
            grp = row.get("groupBy") or row.get("groupedBy")
            if isinstance(grp, dict):
                model = grp.get("model")
                if model:
                    summary.by_model[model] = summary.by_model.get(model, 0) + val
        return summary

    def query_usage(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        app_id: Optional[str] = None,
        since: Optional[float] = None,
    ) -> MeteredUsageSummary:
        """Aggregates metered usage across criteria."""
        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            try:
                params: Dict[str, Any] = {"from": int(since * 1000) if since else 0}
                if user_id:
                    params["subject"] = f"user:{user_id}"
                resp = self._http_client().get(
                    "/api/v1/meters/token_consumption/query",
                    params=params,
                    headers=self._auth_headers(),
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return self._build_summary_from_openmeter_response(
                        data, user_id, tenant_id, app_id
                    )
                fail_closed_in_production(
                    "openmeter",
                    f"OpenMeter query returned HTTP {resp.status_code}: {resp.text}",
                )
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production("openmeter", f"OpenMeter query failed: {exc}", cause=exc)

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

