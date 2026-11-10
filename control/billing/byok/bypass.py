"""
BYOK Credit Bypass & Quota Tracking Engine (Features 13.06, 13.10).

Features:
- 13.06: BYOK (Bring Your Own Key) zero-platform cost routing: routes requests to user's
  supplied credential and bypasses platform billing / credit deductions.
- 13.10: OpenMeter BYOK event attribution: meters all token usage with `byok=True, billable=False`,
  maintaining real-time rate limit and quota monitoring without billing the user.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

from control.billing.models import TokenUsageEvent

logger = logging.getLogger("control.billing.byok")


class BYOKBypass:
    """
    Decides whether model invocation should be billed to platform balance
    and feeds OpenMeter with accurate BYOK / billable attribution flags.
    """

    def __init__(
        self,
        openmeter_adapter: Optional[Any] = None,
        lago_adapter: Optional[Any] = None,
    ) -> None:
        self._openmeter = openmeter_adapter
        self._lago = lago_adapter
        # Local usage tracking per user
        self._user_usage: Dict[str, Dict[str, int]] = {}  # user_id -> {'total': 0, 'byok': 0, 'billable': 0}

    def _get_openmeter(self) -> Any:
        if self._openmeter is None:
            try:
                from control.billing.metering.openmeter_adapter import default_openmeter_adapter
                self._openmeter = default_openmeter_adapter
            except ImportError:
                pass
        return self._openmeter

    def _get_lago(self) -> Any:
        if self._lago is None:
            try:
                from control.billing.engine.lago_adapter import default_lago_adapter
                self._lago = default_lago_adapter
            except ImportError:
                pass
        return self._lago

    def should_bill(
        self,
        user_id: str,
        provider_key_source: str,
        tokens: int = 0,
        model: str = "unknown",
        tenant_id: str = "default",
        cost_usd: float = 0.0,
    ) -> bool:
        """
        Core BYOK decision algorithm (Features 13.06, 13.10):
        If provider_key_source == "byok":
          - Emits OpenMeter event with byok=True, billable=False.
          - Tracks quota & tokens consumed.
          - Bypasses Lago wallet deduction and returns False.
        Else:
          - Emits OpenMeter event with byok=False, billable=True.
          - Deducts from Lago wallet/subscription.
          - Returns True.
        """
        is_byok = (provider_key_source.strip().lower() == "byok")
        billable = not is_byok

        # 1. Update internal quota & usage counters
        if user_id not in self._user_usage:
            self._user_usage[user_id] = {"total": 0, "byok": 0, "billable": 0}

        self._user_usage[user_id]["total"] += tokens
        if is_byok:
            self._user_usage[user_id]["byok"] += tokens
        else:
            self._user_usage[user_id]["billable"] += tokens

        # 2. Record CloudEvent in OpenMeter
        openmeter = self._get_openmeter()
        event = TokenUsageEvent(
            event_id=str(uuid4()),
            user_id=user_id,
            tenant_id=tenant_id,
            model=model,
            total_tokens=tokens,
            prompt_tokens=int(tokens * 0.4),
            completion_tokens=int(tokens * 0.6),
            cost_usd=0.0 if is_byok else cost_usd,
            byok=is_byok,
            billable=billable,
            metadata={"key_source": provider_key_source},
        )

        if openmeter and hasattr(openmeter, "record_event"):
            try:
                openmeter.record_event(event, dispatch_remote=False)
            except Exception as e:
                logger.debug("Failed dispatching event to OpenMeter: %s", e)

        # 3. Bill via Lago only if billable (not BYOK)
        if billable:
            lago = self._get_lago()
            if lago and hasattr(lago, "record_usage"):
                try:
                    lago.record_usage(customer_id=user_id, tokens=tokens)
                except Exception as e:
                    logger.debug("Failed recording usage in Lago: %s", e)
            return True
        else:
            logger.info("BYOK detected for user '%s': bypassed platform billing for %d tokens.", user_id, tokens)
            return False

    def get_user_usage(self, user_id: str) -> Dict[str, int]:
        """Returns total, BYOK, and billable tokens consumed by user."""
        return self._user_usage.get(user_id, {"total": 0, "byok": 0, "billable": 0})


# Global default singleton
default_byok_bypass = BYOKBypass()
