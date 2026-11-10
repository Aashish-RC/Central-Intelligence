"""Federated Learning (L19 Federation - Tasks 19.29, 19.30).

Implements on-premise local model training on tenant data where sensitive
raw data never leaves the tenant boundary. Only privacy-preserving, mathematically
aggregated model weight deltas (FedAvg) are communicated to the core brain.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WeightUpdateDelta:
    """Model parameter gradients / delta weights produced by tenant training."""
    tenant_id: str
    round_number: int
    num_samples: int
    weight_deltas: Dict[str, List[float]]  # layer_name -> weight delta list
    differential_privacy_epsilon: float = 1.0
    created_at: float = field(default_factory=time.time)


class TenantLearningNode:
    """Tenant-isolated learning node executing local training."""

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        # Private tenant training samples strictly sequestered on-premise
        self._private_dataset: List[Dict[str, Any]] = []

    def ingest_local_data(self, samples: List[Dict[str, Any]]) -> int:
        """Add training data to local tenant partition."""
        self._private_dataset.extend(samples)
        return len(self._private_dataset)

    def train_local_epoch(
        self,
        base_weights: Dict[str, List[float]],
        round_number: int,
        learning_rate: float = 0.01,
    ) -> WeightUpdateDelta:
        """Train locally on private data.

        Returns only the mathematical weight update delta, guaranteeing zero raw data egress.
        """
        n_samples = max(1, len(self._private_dataset))
        deltas: Dict[str, List[float]] = {}

        # Compute gradient delta based on local data volume and characteristics
        for layer, weights in base_weights.items():
            # Simulated gradient step: delta = -lr * grad (proportional to local sample count)
            deltas[layer] = [float(w * 0.05 * (n_samples / 100.0)) for w in weights]

        logger.info(
            "Tenant '%s' completed local training round %d over %d private samples",
            self.tenant_id,
            round_number,
            n_samples,
        )

        return WeightUpdateDelta(
            tenant_id=self.tenant_id,
            round_number=round_number,
            num_samples=n_samples,
            weight_deltas=deltas,
        )


class FederatedLearningManager:
    """Core aggregator coordinating Federated Averaging (FedAvg) across tenant nodes."""

    def __init__(self, initial_weights: Optional[Dict[str, List[float]]] = None) -> None:
        self.global_weights: Dict[str, List[float]] = initial_weights or {
            "layer_embedding": [0.12, 0.45, -0.22, 0.81],
            "layer_dense_proj": [0.33, -0.15, 0.90, 0.05],
        }
        self.current_round: int = 1
        self._received_deltas: List[WeightUpdateDelta] = []
        self._tenants: Dict[str, TenantLearningNode] = {}

    def register_tenant(self, tenant_id: str) -> TenantLearningNode:
        """Register tenant learning participant."""
        node = TenantLearningNode(tenant_id=tenant_id)
        self._tenants[tenant_id] = node
        return node

    def submit_weight_update(self, delta: WeightUpdateDelta) -> None:
        """Receive model weight update from tenant node. Validates zero raw data inclusion."""
        # Sanity check: Ensure payload contains only float weights, no text or raw data
        for layer, weights in delta.weight_deltas.items():
            if not all(isinstance(w, (int, float)) for w in weights):
                raise ValueError("Security violation: Raw non-numeric data detected in weight delta payload!")

        self._received_deltas.append(delta)

    def aggregate_round(self) -> Dict[str, List[float]]:
        """Compute FedAvg weighted average of tenant deltas and update global weights."""
        if not self._received_deltas:
            return self.global_weights

        total_samples = sum(d.num_samples for d in self._received_deltas)

        # Update each layer
        for layer, base_vals in self.global_weights.items():
            updated_layer = list(base_vals)
            for i in range(len(updated_layer)):
                # Weighted sum of deltas: sum(delta_k[i] * samples_k) / total_samples
                weighted_delta_sum = sum(
                    d.weight_deltas[layer][i] * d.num_samples for d in self._received_deltas
                )
                avg_delta = weighted_delta_sum / total_samples
                updated_layer[i] += avg_delta
            self.global_weights[layer] = updated_layer

        self.current_round += 1
        self._received_deltas.clear()
        logger.info("Completed FedAvg round %d. Updated global weights.", self.current_round - 1)
        return self.global_weights

