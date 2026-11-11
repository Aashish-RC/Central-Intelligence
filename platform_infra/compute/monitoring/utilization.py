"""Real-Time GPU/CPU/Memory Utilization Monitor (L16 Compute - Feature 16.11).

Collects telemetry across compute nodes, answers per-node and cluster-wide GPU
utilization queries, and generates autoscaling signals for orchestrators.
"""

from __future__ import annotations

import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Dict, List


class AutoscalingAction(str, Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    HOLD = "hold"


@dataclass
class NodeUtilizationSample:
    """Point-in-time hardware utilization snapshot for one compute node."""

    node_id: str
    gpu_util_pct: float
    gpu_memory_used_gb: float
    gpu_memory_total_gb: float
    cpu_util_pct: float
    ram_used_gb: float
    ram_total_gb: float
    active_requests: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def gpu_memory_pct(self) -> float:
        if self.gpu_memory_total_gb <= 0:
            return 0.0
        return round((self.gpu_memory_used_gb / self.gpu_memory_total_gb) * 100.0, 2)


@dataclass
class ClusterUtilizationSummary:
    """Cluster-wide aggregated utilization metrics."""

    node_count: int
    avg_gpu_util_pct: float
    max_gpu_util_pct: float
    avg_gpu_memory_pct: float
    avg_cpu_util_pct: float
    total_active_requests: int
    per_node_gpu_pct: Dict[str, float]


@dataclass
class AutoscalingRecommendation:
    """Autoscaling action computed from utilization watermarks."""

    action: AutoscalingAction
    current_replicas: int
    recommended_replicas: int
    avg_gpu_util_pct: float
    reason: str


class UtilizationMonitor:
    """Tracks hardware utilization across inference nodes and guides autoscaling."""

    def __init__(
        self,
        window_size: int = 20,
        scale_up_gpu_pct: float = 80.0,
        scale_down_gpu_pct: float = 20.0,
        min_replicas: int = 1,
        max_replicas: int = 32,
    ) -> None:
        self.window_size = window_size
        self.scale_up_gpu_pct = scale_up_gpu_pct
        self.scale_down_gpu_pct = scale_down_gpu_pct
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self._samples: Dict[str, Deque[NodeUtilizationSample]] = {}

    def record_sample(self, sample: NodeUtilizationSample) -> None:
        """Record latest telemetry sample for a node."""
        buf = self._samples.setdefault(sample.node_id, deque(maxlen=self.window_size))
        buf.append(sample)

    def get_node_latest(self, node_id: str) -> NodeUtilizationSample:
        """Return most recent sample for a specific node."""
        if node_id not in self._samples or not self._samples[node_id]:
            raise KeyError(f"No telemetry recorded for node '{node_id}'")
        return self._samples[node_id][-1]

    def get_all_gpu_utilization(self) -> Dict[str, float]:
        """Query current GPU utilization percentage across every tracked node."""
        return {
            nid: buf[-1].gpu_util_pct
            for nid, buf in self._samples.items()
            if buf
        }

    def query_cluster_summary(self) -> ClusterUtilizationSummary:
        """Aggregate latest telemetry across all active compute nodes."""
        latest = [buf[-1] for buf in self._samples.values() if buf]
        if not latest:
            return ClusterUtilizationSummary(
                node_count=0,
                avg_gpu_util_pct=0.0,
                max_gpu_util_pct=0.0,
                avg_gpu_memory_pct=0.0,
                avg_cpu_util_pct=0.0,
                total_active_requests=0,
                per_node_gpu_pct={},
            )
        return ClusterUtilizationSummary(
            node_count=len(latest),
            avg_gpu_util_pct=round(statistics.mean(s.gpu_util_pct for s in latest), 2),
            max_gpu_util_pct=round(max(s.gpu_util_pct for s in latest), 2),
            avg_gpu_memory_pct=round(statistics.mean(s.gpu_memory_pct for s in latest), 2),
            avg_cpu_util_pct=round(statistics.mean(s.cpu_util_pct for s in latest), 2),
            total_active_requests=sum(s.active_requests for s in latest),
            per_node_gpu_pct={s.node_id: s.gpu_util_pct for s in latest},
        )

    def recommend_autoscaling(self, current_replicas: int) -> AutoscalingRecommendation:
        """Compute scale_up / scale_down / hold decision based on GPU watermarks."""
        summary = self.query_cluster_summary()
        if summary.node_count == 0:
            return AutoscalingRecommendation(
                action=AutoscalingAction.HOLD,
                current_replicas=current_replicas,
                recommended_replicas=current_replicas,
                avg_gpu_util_pct=0.0,
                reason="no_telemetry",
            )

        avg_gpu = summary.avg_gpu_util_pct
        if avg_gpu >= self.scale_up_gpu_pct and current_replicas < self.max_replicas:
            target = min(self.max_replicas, max(current_replicas + 1, int(current_replicas * 1.5)))
            return AutoscalingRecommendation(
                action=AutoscalingAction.SCALE_UP,
                current_replicas=current_replicas,
                recommended_replicas=target,
                avg_gpu_util_pct=avg_gpu,
                reason=f"avg_gpu_util {avg_gpu}% >= {self.scale_up_gpu_pct}%",
            )

        if avg_gpu <= self.scale_down_gpu_pct and current_replicas > self.min_replicas:
            target = max(self.min_replicas, current_replicas - 1)
            return AutoscalingRecommendation(
                action=AutoscalingAction.SCALE_DOWN,
                current_replicas=current_replicas,
                recommended_replicas=target,
                avg_gpu_util_pct=avg_gpu,
                reason=f"avg_gpu_util {avg_gpu}% <= {self.scale_down_gpu_pct}%",
            )

        return AutoscalingRecommendation(
            action=AutoscalingAction.HOLD,
            current_replicas=current_replicas,
            recommended_replicas=current_replicas,
            avg_gpu_util_pct=avg_gpu,
            reason="within_target_band",
        )

