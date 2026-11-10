"""
Automated Model Call Refund Pipeline (Layer 13: Feature 13.12).

Features:
- 13.12: Automated refund pipeline for failed model invocations:
  - Detects upstream provider outages, timeouts, and internal errors (500, 502, 503, 504, 529).
  - Automatically restores consumed tokens to customer wallet/quota.
  - Automatically triggers Hyperswitch monetary refunds if micro-payments were captured.
- Wires into Layer 4 (Model Error Handlers) and Layer 13 Hyperswitch / Lago.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger("control.billing.refunds")

PROVIDER_ERROR_CODES = {
    "500", "502", "503", "504", "529",
    "INTERNAL_SERVER_ERROR", "BAD_GATEWAY", "SERVICE_UNAVAILABLE",
    "GATEWAY_TIMEOUT", "PROVIDER_OVERLOADED", "PROVIDER_TIMEOUT",
    "MODEL_OUTAGE", "UPSTREAM_FAILURE",
}


@dataclass
class ModelCallFailure:
    """Details of a failed model execution."""
    call_id: str
    customer_id: str
    tokens_attempted: int
    error_code: str
    error_message: str
    model: str = "unknown"
    tenant_id: str = "default"
    payment_id: Optional[str] = None
    amount_cents: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_provider_error(self) -> bool:
        """Determines if the failure was caused by upstream model provider rather than user."""
        code = str(self.error_code).upper().strip()
        if code in PROVIDER_ERROR_CODES:
            return True
        msg = self.error_message.lower()
        return any(term in msg for term in ["overloaded", "bad gateway", "service unavailable", "upstream", "timeout"])


@dataclass
class RefundResult:
    """Outcome of automated refund processing."""
    refund_id: str
    call_id: str
    customer_id: str
    tokens_refunded: int
    cents_refunded: int
    status: str  # "refunded", "skipped_non_provider_error"
    reason: str
    hyperswitch_refund_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class RefundPipeline:
    """
    Orchestrates automatic compensation and refunds for failed model calls.
    """

    def __init__(
        self,
        lago_adapter: Optional[Any] = None,
        hyperswitch_adapter: Optional[Any] = None,
        openmeter_adapter: Optional[Any] = None,
    ) -> None:
        self._lago = lago_adapter
        self._hyperswitch = hyperswitch_adapter
        self._openmeter = openmeter_adapter
        self._refund_history: List[RefundResult] = []

    def _get_lago(self) -> Any:
        if self._lago is None:
            try:
                from control.billing.engine.lago_adapter import default_lago_adapter
                self._lago = default_lago_adapter
            except ImportError:
                pass
        return self._lago

    def _get_hyperswitch(self) -> Any:
        if self._hyperswitch is None:
            try:
                from control.billing.payments.hyperswitch_adapter import default_hyperswitch_adapter
                self._hyperswitch = default_hyperswitch_adapter
            except ImportError:
                pass
        return self._hyperswitch

    def _get_openmeter(self) -> Any:
        if self._openmeter is None:
            try:
                from control.billing.metering.openmeter_adapter import default_openmeter_adapter
                self._openmeter = default_openmeter_adapter
            except ImportError:
                pass
        return self._openmeter

    def process_failed_call(self, failure: ModelCallFailure) -> RefundResult:
        """
        Evaluates a failed model call and automatically triggers token / payment refunds
        if the failure is attributable to the model provider (Feature 13.12).
        """
        if not failure.is_provider_error():
            logger.info("Call %s failed with non-provider error (%s); skipping auto-refund.", failure.call_id, failure.error_code)
            return RefundResult(
                refund_id=f"ref_skip_{uuid4().hex[:8]}",
                call_id=failure.call_id,
                customer_id=failure.customer_id,
                tokens_refunded=0,
                cents_refunded=0,
                status="skipped_non_provider_error",
                reason=f"Error {failure.error_code} is a user/client error, not an upstream provider outage.",
            )

        # 1. Automatically restore consumed tokens in Lago subscription
        lago = self._get_lago()
        if lago and hasattr(lago, "_subscriptions") and failure.customer_id in lago._subscriptions:
            sub = lago._subscriptions[failure.customer_id]
            # Reduce usage counter or credit back
            sub.tokens_used_this_period = max(0, sub.tokens_used_this_period - failure.tokens_attempted)
            logger.info("Auto-refunded %d tokens to customer '%s' in Lago.", failure.tokens_attempted, failure.customer_id)

        # 2. If a monetary payment was captured via Hyperswitch, refund it
        hs_refund_id = None
        cents_refunded = 0
        if failure.payment_id and failure.amount_cents > 0:
            hs = self._get_hyperswitch()
            if hs and hasattr(hs, "refund_payment"):
                try:
                    rf_rec = hs.refund_payment(
                        payment_id=failure.payment_id,
                        amount_cents=failure.amount_cents,
                        reason=f"Auto-refund: provider error {failure.error_code} on call {failure.call_id}",
                    )
                    hs_refund_id = getattr(rf_rec, "refund_id", str(uuid4()))
                    cents_refunded = failure.amount_cents
                except Exception as e:
                    logger.error("Failed refunding Hyperswitch payment %s: %s", failure.payment_id, e)

        # 3. Mirror negative adjustment in OpenMeter
        openmeter = self._get_openmeter()
        if openmeter and hasattr(openmeter, "record_event"):
            try:
                from control.billing.models import TokenUsageEvent
                event = TokenUsageEvent(
                    event_id=f"adj_{uuid4().hex[:12]}",
                    user_id=failure.customer_id,
                    tenant_id=failure.tenant_id,
                    model=failure.model,
                    total_tokens=-failure.tokens_attempted,
                    cost_usd=0.0,
                    billable=False,
                    metadata={"adjustment_type": "refund_provider_failure", "call_id": failure.call_id},
                )
                openmeter.record_event(event, dispatch_remote=False)
            except Exception:
                pass

        result = RefundResult(
            refund_id=f"ref_{uuid4().hex[:10]}",
            call_id=failure.call_id,
            customer_id=failure.customer_id,
            tokens_refunded=failure.tokens_attempted,
            cents_refunded=cents_refunded,
            status="refunded",
            reason=f"Automated refund for provider outage ({failure.error_code}: {failure.error_message}).",
            hyperswitch_refund_id=hs_refund_id,
        )
        self._refund_history.append(result)
        logger.warning(
            "Auto-refund completed for call %s: %d tokens and %d cents restored to customer %s",
            failure.call_id,
            result.tokens_refunded,
            result.cents_refunded,
            failure.customer_id,
        )
        return result

    def get_refund_history(self, customer_id: Optional[str] = None) -> List[RefundResult]:
        if customer_id:
            return [r for r in self._refund_history if r.customer_id == customer_id]
        return list(self._refund_history)


# Global default singleton
default_refund_pipeline = RefundPipeline()
