"""Consent Gate for Federated Brain Sync (L19 Federation - Task 19.3).

Ensures sensitive specialized domain output (e.g. Legal privileged drafts,
medical telemetry, executive strategy) cannot be pulled or federated without explicit consent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Set

logger = logging.getLogger(__name__)


class ConsentDeniedError(Exception):
    """Raised when federated data pull is attempted without explicit consent."""
    pass


class ConsentGate:
    """Manages authorization grants for federated data synchronization."""

    def __init__(self) -> None:
        # brain_id -> set of consented data_types
        self._grants: Dict[str, Set[str]] = {}

    def grant_consent(self, brain_id: str, data_type: str) -> None:
        """Explicitly authorize data type for brain federation."""
        if brain_id not in self._grants:
            self._grants[brain_id] = set()
        self._grants[brain_id].add(data_type)
        logger.info("Granted consent for brain '%s' on data type '%s'", brain_id, data_type)

    def revoke_consent(self, brain_id: str, data_type: str) -> None:
        """Revoke authorization."""
        if brain_id in self._grants:
            self._grants[brain_id].discard(data_type)

    def is_granted(self, brain_id: str, data_type: str) -> bool:
        """Check if consent grant exists for this brain and data type."""
        brain_grants = self._grants.get(brain_id, set())
        return data_type in brain_grants or "*" in brain_grants
