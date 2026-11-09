"""Identity Financial Authority Bridge (Layer 12: IAM, Feature 12.45).

Bridges user identity, tenant financial governance, and agent spending rights
to L5's Financial Authority Guard (cognitive.action.safety.financial_authority).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cognitive.action.safety.financial_authority import (
    AgentFinancialPolicy,
    FinancialAuthorityError,
    FinancialAuthorityGuard,
    TransactionRecord,
    TransactionStatus,
)

logger = logging.getLogger("control.identity.financial")


@dataclass
class UserFinancialAuthority:
    """Identity-level spending authority bounds for a user."""
    user_id: str
    tenant_id: str
    max_single_transaction_usd: float
    daily_budget_usd: float
    spent_today_usd: float = 0.0
    last_reset_day: int = field(default_factory=lambda: int(time.time()) // 86400)
    dual_control_threshold_usd: float = 1000.0


@dataclass
class PaymentAuthorizationResult:
    """Result of spending check and transaction authorization."""
    authorized: bool
    transaction_id: str
    user_id: str
    agent_id: str
    amount_usd: float
    status: TransactionStatus
    receipt_token: Optional[str] = None
    reason: str = ""


class IdentityFinancialBridge:
    """Bridges L12 user spend limits to L5 FinancialAuthorityGuard."""

    def __init__(self, financial_guard: Optional[FinancialAuthorityGuard] = None):
        self.guard = financial_guard or FinancialAuthorityGuard()
        self._user_authorities: Dict[str, UserFinancialAuthority] = {}

    def set_user_limit(
        self,
        user_id: str,
        max_single_transaction_usd: float,
        daily_budget_usd: float,
        tenant_id: str = "default",
        dual_control_threshold_usd: float = 1000.0,
    ) -> UserFinancialAuthority:
        auth = UserFinancialAuthority(
            user_id=user_id,
            tenant_id=tenant_id,
            max_single_transaction_usd=max_single_transaction_usd,
            daily_budget_usd=daily_budget_usd,
            dual_control_threshold_usd=dual_control_threshold_usd,
        )
        self._user_authorities[user_id] = auth
        return auth

    def get_user_authority(self, user_id: str) -> Optional[UserFinancialAuthority]:
        return self._user_authorities.get(user_id)

    def check_and_authorize_payment(
        self,
        user_id: str,
        agent_id: str,
        amount_usd: float,
        recipient: str,
        purpose: str,
    ) -> PaymentAuthorizationResult:
        """Verifies user's spend limit before calling L5 FinancialAuthorityGuard."""
        user_auth = self._user_authorities.get(user_id)
        if not user_auth:
            # Default fallback conservative limit if not explicitly defined
            user_auth = self.set_user_limit(
                user_id=user_id,
                max_single_transaction_usd=100.0,
                daily_budget_usd=500.0,
            )

        # Reset daily spend counter if a new day has rolled over
        current_day = int(time.time()) // 86400
        if current_day > user_auth.last_reset_day:
            user_auth.spent_today_usd = 0.0
            user_auth.last_reset_day = current_day

        # 1. Enforce user-level single transaction limit
        if amount_usd > user_auth.max_single_transaction_usd:
            raise FinancialAuthorityError(
                f"Transaction amount ${amount_usd:.2f} exceeds user's single transaction limit of ${user_auth.max_single_transaction_usd:.2f}"
            )

        # 2. Enforce user-level daily budget limit
        if (user_auth.spent_today_usd + amount_usd) > user_auth.daily_budget_usd:
            raise FinancialAuthorityError(
                f"Transaction amount ${amount_usd:.2f} would exceed user's daily budget of ${user_auth.daily_budget_usd:.2f} (already spent today: ${user_auth.spent_today_usd:.2f})"
            )

        # 3. Synchronize with agent policy in L5 guard
        if agent_id not in self.guard._policies:
            self.guard.set_policy(
                AgentFinancialPolicy(
                    agent_id=agent_id,
                    max_single_transaction_usd=user_auth.max_single_transaction_usd,
                    daily_budget_usd=user_auth.daily_budget_usd,
                    monthly_budget_usd=user_auth.daily_budget_usd * 30,
                    dual_control_threshold_usd=user_auth.dual_control_threshold_usd,
                )
            )

        # 4. Request transaction authorization from L5 guard
        tx_rec: TransactionRecord = self.guard.evaluate_transaction(
            agent_id=agent_id,
            amount_usd=amount_usd,
            recipient=recipient,
            purpose=purpose,
        )

        if tx_rec.status in (TransactionStatus.APPROVED, TransactionStatus.SETTLED):
            user_auth.spent_today_usd += amount_usd
            receipt_token = f"rcpt_{tx_rec.transaction_id}"
            return PaymentAuthorizationResult(
                authorized=True,
                transaction_id=tx_rec.transaction_id,
                user_id=user_id,
                agent_id=agent_id,
                amount_usd=amount_usd,
                status=tx_rec.status,
                receipt_token=receipt_token,
                reason="Payment authorized within limits",
            )
        else:
            return PaymentAuthorizationResult(
                authorized=False,
                transaction_id=tx_rec.transaction_id,
                user_id=user_id,
                agent_id=agent_id,
                amount_usd=amount_usd,
                status=tx_rec.status,
                reason="; ".join(tx_rec.reasons) or "Transaction blocked or pending approval",
            )


# Default singleton
default_identity_financial_bridge = IdentityFinancialBridge()
