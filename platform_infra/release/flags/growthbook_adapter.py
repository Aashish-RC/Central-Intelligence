"""GrowthBook Feature Flags Adapter (L17 Release & Lifecycle - Task 17.3).

Provides feature toggles, percentage-based canary rollouts, and deterministic
A/B experimentation consistent with GrowthBook SDK conventions.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    is_production,
    require_live_adapter,
)

logger = logging.getLogger(__name__)


@dataclass
class FeatureFlag:
    """Descriptor for feature flag and canary rollout rule."""
    key: str
    enabled: bool = True
    # Rollout percentage: 0.0 to 100.0 (e.g. 5.0 for a 5% canary)
    rollout_percentage: float = 100.0
    value: Any = True
    fallback_value: Any = False
    targeting_attributes: Dict[str, Any] = field(default_factory=dict)
    variations: List[Any] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """Result of evaluating a feature flag for a user context."""
    key: str
    is_on: bool
    value: Any
    in_experiment: bool = False
    variation_id: Optional[int] = None
    bucket_hash: float = 0.0


class GrowthBookAdapter:
    """Adapter for GrowthBook feature flagging and canary rollouts."""

    def __init__(
        self,
        api_host: Optional[str] = None,
        client_key: Optional[str] = None,
    ) -> None:
        self.api_host = (api_host or os.getenv("GROWTHBOOK_API_HOST", "https://app.growthbook.io")).rstrip("/")
        self.client_key = client_key if client_key is not None else os.getenv("GROWTHBOOK_CLIENT_KEY", "")
        self.adapter_mode = require_live_adapter(
            "growthbook",
            require_credentials={"client_key": self.client_key},
        )
        self._flags: Dict[str, FeatureFlag] = {}

    def sync_features(self) -> int:
        """Fetch live feature definitions from GrowthBook API."""
        self.adapter_mode = require_live_adapter(
            "growthbook",
            require_credentials={"client_key": self.client_key},
        )
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.api_host}/api/features/{self.client_key}")
                if resp.status_code == 200:
                    features = resp.json().get("features", {})
                    for key, spec in features.items():
                        self._flags[key] = FeatureFlag(
                            key=key,
                            enabled=True,
                            value=spec.get("defaultValue", True),
                        )
                    return len(features)
                fail_closed_in_production("growthbook", f"GrowthBook API returned HTTP {resp.status_code}")
        except ProductionSafetyError:
            raise
        except Exception as exc:
            fail_closed_in_production("growthbook", f"GrowthBook feature sync failed: {exc}", cause=exc)
        return len(self._flags)

    def register_flag(self, flag: FeatureFlag) -> None:
        """Register or update a feature flag definition."""
        self._flags[flag.key] = flag

    def toggle_flag(self, key: str, enabled: bool) -> bool:
        """Toggle global flag enable state."""
        if key not in self._flags:
            self._flags[key] = FeatureFlag(key=key, enabled=enabled)
            return enabled
        self._flags[key].enabled = enabled
        return enabled

    def set_rollout_percentage(self, key: str, percentage: float) -> None:
        """Set canary rollout percentage (0.0 to 100.0)."""
        if key not in self._flags:
            self._flags[key] = FeatureFlag(key=key, rollout_percentage=percentage)
        else:
            self._flags[key].rollout_percentage = max(0.0, min(100.0, percentage))

    def _hash_bucket(self, user_id: str, seed: str) -> float:
        """Compute deterministic bucket float between 0.0 and 100.0 using SHA256."""
        raw = f"{user_id}:{seed}".encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        # Take first 8 chars as int, map into [0, 100)
        val = int(digest[:8], 16)
        return (val % 10000) / 100.0

    def evaluate(self, key: str, user_id: str, attributes: Optional[Dict[str, Any]] = None) -> EvaluationResult:
        """Evaluate flag for a user against status, canary rollout, and variations."""
        if key not in self._flags:
            return EvaluationResult(key=key, is_on=False, value=False)

        flag = self._flags[key]

        # 1. If globally disabled -> OFF
        if not flag.enabled:
            return EvaluationResult(key=key, is_on=False, value=flag.fallback_value)

        # 2. Percentage canary rollout evaluation
        bucket = self._hash_bucket(user_id=user_id, seed=key)
        if bucket >= flag.rollout_percentage:
            # User outside canary window
            return EvaluationResult(
                key=key,
                is_on=False,
                value=flag.fallback_value,
                bucket_hash=bucket,
            )

        # 3. User inside canary window
        variation_id = None
        resolved_value = flag.value
        if flag.variations:
            # A/B test split among variations
            var_idx = int(bucket) % len(flag.variations)
            variation_id = var_idx
            resolved_value = flag.variations[var_idx]

        return EvaluationResult(
            key=key,
            is_on=True,
            value=resolved_value,
            in_experiment=bool(flag.variations),
            variation_id=variation_id,
            bucket_hash=bucket,
        )

    def is_on(self, key: str, user_id: str) -> bool:
        """Convenience method checking boolean flag status."""
        return self.evaluate(key, user_id).is_on

