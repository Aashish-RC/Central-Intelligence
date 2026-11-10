"""Training Consent Manager (Feature 7.21)

Enforces per-user opt-in/opt-out policies for model fine-tuning and training corpora.
Directly wires with Layer 10 c15t consent management adapter.
"""

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional

try:
    from control.safety.consent.c15t_adapter import C15tConsentAdapter, ConsentPurpose
except ImportError:
    C15tConsentAdapter = Any  # type: ignore
    ConsentPurpose = Any      # type: ignore


class TrainingConsentManager:
    """Manages training data consent policies and dataset compliance filtering."""

    def __init__(self, c15t_adapter: Optional[C15tConsentAdapter] = None) -> None:
        if c15t_adapter is not None:
            self.c15t = c15t_adapter
        else:
            try:
                from control.safety.consent.c15t_adapter import C15tConsentAdapter
                self.c15t = C15tConsentAdapter(default_opt_in=False)
            except Exception:
                self.c15t = None

        self._local_overrides: Dict[str, bool] = {}

    def can_use_for_training(self, user_id: str, tenant_id: str = "default") -> bool:
        """Check whether a user's data can legally be used for model training."""
        # Check explicit local override if present
        if user_id in self._local_overrides:
            return self._local_overrides[user_id]

        if self.c15t is not None:
            # Query L10 c15t consent record
            record = self.c15t.get_consent_record(user_id, tenant_id)
            if record.privacy_mode:
                return False
            purpose = "model_training"
            return bool(record.purposes.get(purpose, False))

        return False

    def set_user_training_consent(self, user_id: str, opt_in: bool, tenant_id: str = "default") -> None:
        """Explicitly set training consent for a user."""
        self._local_overrides[user_id] = opt_in
        if self.c15t is not None:
            if opt_in:
                self.c15t.grant_consent(user_id=user_id, purposes=["model_training"], tenant_id=tenant_id)
            else:
                self.c15t.revoke_consent(user_id=user_id, purposes=["model_training"], tenant_id=tenant_id)

    def filter_dataset_by_consent(
        self,
        dataset: List[Dict[str, Any]],
        user_id_key: str = "user_id",
    ) -> List[Dict[str, Any]]:
        """Filter a collection of data samples to strictly exclude opted-out users."""
        approved_samples: List[Dict[str, Any]] = []

        for item in dataset:
            user_id = item.get(user_id_key) or item.get("metadata", {}).get("user_id")
            if not user_id:
                # Without identifiable consent provenance, omit from training
                continue

            tenant_id = item.get("tenant_id") or item.get("metadata", {}).get("tenant_id", "default")
            if self.can_use_for_training(user_id, tenant_id):
                approved_samples.append(item)

        return approved_samples

