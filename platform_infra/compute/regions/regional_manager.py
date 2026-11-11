"""Regional Serving, Data Residency & Traffic Distribution (L16 Compute - 16.18, 16.19, 16.21).

Routes inference requests to the nearest healthy regional node while strictly
enforcing data-residency boundaries (e.g., EU requests remain within EU zones)
and capacity-weighted traffic distribution across compliant replicas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class ResidencyViolationError(RuntimeError):
    """Raised when no healthy compute region satisfies required data residency."""


@dataclass
class RegionNode:
    """Compute serving region node with geo-coordinates and capacity metadata."""

    region_id: str
    residency_zone: str  # e.g., "EU", "US", "APAC"
    endpoint_url: str
    latitude: float
    longitude: float
    weight: float = 1.0
    capacity_rps: int = 100
    current_load_rps: int = 0
    healthy: bool = True
    supported_models: List[str] = field(default_factory=list)


@dataclass
class RoutingRequest:
    """Incoming regional inference routing request."""

    request_id: str
    model_id: str
    user_latitude: float
    user_longitude: float
    required_residency: Optional[str] = None
    preferred_region: Optional[str] = None


@dataclass
class PlacementDecision:
    """Selected regional endpoint and routing rationale."""

    region_id: str
    residency_zone: str
    endpoint_url: str
    distance_km: float
    strategy: str


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon pairs in kilometers."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2
    return round(2 * r * math.asin(min(1.0, math.sqrt(a))), 2)


class RegionalServingManager:
    """Routes traffic by residency policy, nearest geo-distance, and headroom."""

    def __init__(self) -> None:
        self._nodes: Dict[str, RegionNode] = {}
        self._routed_counts: Dict[str, int] = {}

    def register_node(self, node: RegionNode) -> None:
        self._nodes[node.region_id] = node
        self._routed_counts.setdefault(node.region_id, 0)

    def set_health(self, region_id: str, healthy: bool) -> None:
        self._nodes[region_id].healthy = healthy

    def update_load(self, region_id: str, current_load_rps: int) -> None:
        self._nodes[region_id].current_load_rps = max(0, current_load_rps)

    def route(self, req: RoutingRequest) -> PlacementDecision:
        """Select optimal compliant region for the request."""
        candidates = [
            n
            for n in self._nodes.values()
            if n.healthy
            and (not n.supported_models or req.model_id in n.supported_models)
            and n.current_load_rps < n.capacity_rps
        ]

        if req.required_residency:
            compliant = [
                n for n in candidates if n.residency_zone.upper() == req.required_residency.upper()
            ]
            if not compliant:
                raise ResidencyViolationError(
                    f"No healthy node satisfies data residency '{req.required_residency}' for model '{req.model_id}'"
                )
            candidates = compliant

        if not candidates:
            raise RuntimeError(f"No healthy regional capacity available for model '{req.model_id}'")

        # Score candidates primarily by distance, breaking ties / shifting on near-equal loads by headroom * weight
        scored: List[Tuple[float, float, RegionNode]] = []
        for node in candidates:
            dist = _haversine_km(req.user_latitude, req.user_longitude, node.latitude, node.longitude)
            headroom = max(0.05, 1.0 - (node.current_load_rps / max(node.capacity_rps, 1)))
            # Prefer exact preferred_region if compliant and has headroom
            pref_bonus = 0.0 if req.preferred_region == node.region_id else 50.0
            score = dist + pref_bonus - (headroom * node.weight * 25.0)
            scored.append((score, dist, node))

        scored.sort(key=lambda item: item[0])
        _, chosen_dist, chosen = scored[0]
        self._routed_counts[chosen.region_id] = self._routed_counts.get(chosen.region_id, 0) + 1
        strategy = "residency_nearest" if req.required_residency else "nearest_geo_weighted"

        return PlacementDecision(
            region_id=chosen.region_id,
            residency_zone=chosen.residency_zone,
            endpoint_url=chosen.endpoint_url,
            distance_km=chosen_dist,
            strategy=strategy,
        )

    def distribute_traffic(self, total_requests: int, residency_zone: Optional[str] = None) -> Dict[str, int]:
        """Compute capacity-and-weight proportional traffic allocation across healthy regions."""
        pool = [
            n
            for n in self._nodes.values()
            if n.healthy and (residency_zone is None or n.residency_zone.upper() == residency_zone.upper())
        ]
        if not pool or total_requests <= 0:
            return {}
        effective = {n.region_id: max(1.0, n.weight * max(1, n.capacity_rps - n.current_load_rps)) for n in pool}
        total_weight = sum(effective.values())
        allocation: Dict[str, int] = {}
        assigned = 0
        ordered = list(effective.items())
        for idx, (rid, w) in enumerate(ordered):
            if idx == len(ordered) - 1:
                allocation[rid] = max(0, total_requests - assigned)
            else:
                share = int(round((w / total_weight) * total_requests))
                allocation[rid] = share
                assigned += share
        return allocation

