"""
Bring-Your-Own Infrastructure (BYOI) Compute Metering (Feature 13.08).

Features:
- 13.08: Meters compute execution across distinct targets:
  - Local device (on-device local inference, e.g. Ollama, Metal, local GPU)
  - Peer devices (other devices on user's private mesh/network)
  - Cloud compute (managed cloud GPU, hosted cloud providers)
- Computes real-time workload distribution percentages (e.g. 50% local, 30% other device, 20% cloud).
- Wires into Layer 16 Compute and feeds Layer 13 OpenMeter token metering.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger("control.billing.byoi")


class ComputeTargetType(str, Enum):
    LOCAL = "local"
    PEER_DEVICE = "peer_device"  # other user devices
    CLOUD = "cloud"
    BYOI_CLUSTER = "byoi_cluster"


@dataclass
class ComputeUsageRecord:
    """Represents a single compute execution metered on a specific target."""
    record_id: str
    user_id: str
    tenant_id: str = "default"
    compute_target: ComputeTargetType = ComputeTargetType.LOCAL
    target_identifier: str = "primary_device"
    tokens: int = 0
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComputeDistribution:
    """Aggregated distribution of compute usage across local, peer devices, and cloud."""
    user_id: str
    total_tokens: int
    total_invocations: int
    by_target_tokens: Dict[str, int]
    by_target_percentage: Dict[str, float]
    by_target_invocations: Dict[str, int]


class BYOInfrastructureMeter:
    """
    Tracks and distributes compute metrics across heterogeneous infrastructure targets.
    """

    def __init__(self, openmeter_adapter: Optional[Any] = None) -> None:
        self._openmeter = openmeter_adapter
        self._records: List[ComputeUsageRecord] = []

    def _get_openmeter(self) -> Any:
        if self._openmeter is None:
            try:
                from control.billing.metering.openmeter_adapter import default_openmeter_adapter
                self._openmeter = default_openmeter_adapter
            except ImportError:
                pass
        return self._openmeter

    def record_compute(
        self,
        user_id: str,
        compute_target: ComputeTargetType | str,
        tokens: int,
        target_identifier: str = "default_device",
        duration_ms: float = 0.0,
        tenant_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ComputeUsageRecord:
        """
        Records a compute execution event on a specific infrastructure target (Feature 13.08).
        """
        target_enum = ComputeTargetType(compute_target) if isinstance(compute_target, str) else compute_target

        rec = ComputeUsageRecord(
            record_id=f"comp_{uuid4().hex[:12]}",
            user_id=user_id,
            tenant_id=tenant_id,
            compute_target=target_enum,
            target_identifier=target_identifier,
            tokens=tokens,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
        self._records.append(rec)

        # Mirror event to OpenMeter with compute_provider attribute
        openmeter = self._get_openmeter()
        if openmeter and hasattr(openmeter, "record_event"):
            try:
                from control.billing.models import TokenUsageEvent
                event = TokenUsageEvent(
                    event_id=rec.record_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    total_tokens=tokens,
                    compute_provider=target_enum.value,
                    metadata={"target_identifier": target_identifier, **(metadata or {})},
                )
                openmeter.record_event(event, dispatch_remote=False)
            except Exception:
                pass

        logger.debug(
            "Metered %d tokens on %s (%s) for user %s",
            tokens,
            target_enum.value,
            target_identifier,
            user_id,
        )
        return rec

    def get_distribution(self, user_id: str) -> ComputeDistribution:
        """
        Calculates compute distribution percentages across local, peer device, and cloud targets.
        (Feature 13.08 acceptance: '50% local, 30% other device, 20% cloud').
        """
        user_records = [r for r in self._records if r.user_id == user_id]

        total_tokens = sum(r.tokens for r in user_records)
        total_invocations = len(user_records)

        target_tokens: Dict[str, int] = {
            ComputeTargetType.LOCAL.value: 0,
            ComputeTargetType.PEER_DEVICE.value: 0,
            ComputeTargetType.CLOUD.value: 0,
        }
        target_invocations: Dict[str, int] = {
            ComputeTargetType.LOCAL.value: 0,
            ComputeTargetType.PEER_DEVICE.value: 0,
            ComputeTargetType.CLOUD.value: 0,
        }

        for r in user_records:
            key = r.compute_target.value
            target_tokens[key] = target_tokens.get(key, 0) + r.tokens
            target_invocations[key] = target_invocations.get(key, 0) + 1

        percentages: Dict[str, float] = {}
        for k, v in target_tokens.items():
            pct = (v / total_tokens * 100.0) if total_tokens > 0 else 0.0
            percentages[k] = round(pct, 2)

        return ComputeDistribution(
            user_id=user_id,
            total_tokens=total_tokens,
            total_invocations=total_invocations,
            by_target_tokens=target_tokens,
            by_target_percentage=percentages,
            by_target_invocations=target_invocations,
        )


# Global default singleton
default_infrastructure_meter = BYOInfrastructureMeter()

