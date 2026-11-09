"""Financial Authority Guard: Budget limits, velocity checks, and dual-control approvals.

Prevents autonomous financial overruns, unauthorized payments, or runaway API
cloud provisioning costs by enforcing hard authority ceilings and dual-control signoffs.

Features: 5.46, 12.45
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import threading
from typing import Dict, List, Optional
import uuid


class TransactionStatus(str, Enum):
    APPROVED = "approved"
    PENDING_APPROVAL = "pending_approval"
    BLOCKED = "blocked"
    SETTLED = "settled"


class FinancialAuthorityError(Exception):
    """Raised when an action violates financial authority limits."""
    pass


@dataclass
class AgentFinancialPolicy:
    """Configured spending bounds and authority for an agent or role."""
    agent_id: str
    max_single_transaction_usd: float
    daily_budget_usd: float
    monthly_budget_usd: float
    dual_control_threshold_usd: float = 1000.0  # Above this, requires 2 signatures
    max_transactions_per_hour: int = 10


@dataclass
class TransactionRecord:
    """Auditable financial transaction entry."""
    transaction_id: str
    agent_id: str
    amount_usd: float
    recipient: str
    purpose: str
    status: TransactionStatus
    reasons: List[str]
    signatures: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class FinancialAuthorityGuard:
    """Enforces financial authority limits, transaction velocity, and multi-sig thresholds."""

    def __init__(self):
        self._mutex = threading.RLock()
        self._policies: Dict[str, AgentFinancialPolicy] = {}
        self._transactions: Dict[str, TransactionRecord] = {}
        # agent_id -> list of timestamps
        self._hourly_velocity: Dict[str, List[float]] = {}
        # agent_id -> total spend today
        self._daily_spend: Dict[str, float] = {}

    def set_policy(self, policy: AgentFinancialPolicy) -> None:
        """Assigns financial spending limits to an agent."""
        with self._mutex:
            self._policies[policy.agent_id] = policy

    def get_policy(self, agent_id: str) -> Optional[AgentFinancialPolicy]:
        with self._mutex:
            return self._policies.get(agent_id)

    def evaluate_transaction(
        self,
        agent_id: str,
        amount_usd: float,
        recipient: str,
        purpose: str,
    ) -> TransactionRecord:
        """Evaluates whether an agent has authority to execute a transaction."""
        with self._mutex:
            policy = self._policies.get(agent_id)
            reasons: List[str] = []
            now = datetime.now(timezone.utc).timestamp()
            tx_id = f"tx_{uuid.uuid4().hex[:8]}"

            if not policy:
                # Default zero-authority policy: block unconfigured agents
                reasons.append(f"Agent '{agent_id}' has no registered financial authority policy.")
                record = TransactionRecord(
                    transaction_id=tx_id,
                    agent_id=agent_id,
                    amount_usd=amount_usd,
                    recipient=recipient,
                    purpose=purpose,
                    status=TransactionStatus.BLOCKED,
                    reasons=reasons,
                )
                self._transactions[tx_id] = record
                return record

            # 1. Negative or zero amount check
            if amount_usd <= 0:
                reasons.append("Transaction amount must be strictly positive.")
                record = TransactionRecord(
                    transaction_id=tx_id,
                    agent_id=agent_id,
                    amount_usd=amount_usd,
                    recipient=recipient,
                    purpose=purpose,
                    status=TransactionStatus.BLOCKED,
                    reasons=reasons,
                )
                self._transactions[tx_id] = record
                return record

            # 2. Check velocity bounds (transactions per hour)
            recent_timestamps = [
                ts for ts in self._hourly_velocity.get(agent_id, [])
                if now - ts < 3600.0
            ]
            self._hourly_velocity[agent_id] = recent_timestamps

            if len(recent_timestamps) >= policy.max_transactions_per_hour:
                reasons.append(
                    f"Velocity limit exceeded: {len(recent_timestamps)} transactions in the past hour "
                    f"(max {policy.max_transactions_per_hour})."
                )
                record = TransactionRecord(
                    transaction_id=tx_id,
                    agent_id=agent_id,
                    amount_usd=amount_usd,
                    recipient=recipient,
                    purpose=purpose,
                    status=TransactionStatus.BLOCKED,
                    reasons=reasons,
                )
                self._transactions[tx_id] = record
                return record

            # 3. Check single transaction cap
            if amount_usd > policy.max_single_transaction_usd:
                reasons.append(
                    f"Amount ${amount_usd:.2f} exceeds single transaction authority cap ${policy.max_single_transaction_usd:.2f}."
                )

            # 4. Check daily budget cap
            current_day_spend = self._daily_spend.get(agent_id, 0.0)
            if current_day_spend + amount_usd > policy.daily_budget_usd:
                reasons.append(
                    f"Total daily spend would reach ${(current_day_spend + amount_usd):.2f}, "
                    f"exceeding daily budget ${policy.daily_budget_usd:.2f}."
                )

            # Determine status based on violations & dual-control threshold
            if reasons:
                status = TransactionStatus.PENDING_APPROVAL
            elif amount_usd >= policy.dual_control_threshold_usd:
                reasons.append(
                    f"Amount ${amount_usd:.2f} exceeds dual-control threshold "
                    f"${policy.dual_control_threshold_usd:.2f}; requires dual authorization signatures."
                )
                status = TransactionStatus.PENDING_APPROVAL
            else:
                status = TransactionStatus.APPROVED

            record = TransactionRecord(
                transaction_id=tx_id,
                agent_id=agent_id,
                amount_usd=amount_usd,
                recipient=recipient,
                purpose=purpose,
                status=status,
                reasons=reasons,
            )
            self._transactions[tx_id] = record
            return record

    def add_authorization_signature(
        self,
        transaction_id: str,
        signer_id: str,
    ) -> TransactionRecord:
        """Adds a cryptographic/supervisor authorization signature to approve a pending transaction."""
        with self._mutex:
            record = self._transactions.get(transaction_id)
            if not record:
                raise KeyError(f"Transaction '{transaction_id}' not found.")

            if signer_id in record.signatures:
                return record

            record.signatures.append(signer_id)
            policy = self._policies.get(record.agent_id)
            dual_threshold = policy.dual_control_threshold_usd if policy else 1000.0

            required_signatures = 2 if record.amount_usd >= dual_threshold else 1

            if len(record.signatures) >= required_signatures:
                record.status = TransactionStatus.APPROVED

            return record

    def settle_transaction(self, transaction_id: str) -> TransactionRecord:
        """Finalizes an approved transaction, recording spend against daily budget."""
        with self._mutex:
            record = self._transactions.get(transaction_id)
            if not record:
                raise KeyError(f"Transaction '{transaction_id}' not found.")

            if record.status != TransactionStatus.APPROVED:
                raise FinancialAuthorityError(
                    f"Cannot settle transaction '{transaction_id}' with status '{record.status.value}'."
                )

            record.status = TransactionStatus.SETTLED
            self._daily_spend[record.agent_id] = (
                self._daily_spend.get(record.agent_id, 0.0) + record.amount_usd
            )
            now = datetime.now(timezone.utc).timestamp()
            self._hourly_velocity.setdefault(record.agent_id, []).append(now)

            return record

    def get_remaining_daily_budget(self, agent_id: str) -> float:
        """Returns the unspent budget allowance for the agent today."""
        with self._mutex:
            policy = self._policies.get(agent_id)
            if not policy:
                return 0.0
            spend = self._daily_spend.get(agent_id, 0.0)
            return max(0.0, policy.daily_budget_usd - spend)
