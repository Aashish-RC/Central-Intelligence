"""Conflict Resolver for Federated Brain Sync (L19 Federation - Task 19.3).

Resolves concurrent data revisions exchanged between federated brains
using deterministic version tracking and structural payload merging.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class BrainConflictResolver:
    """Resolves data version collisions during federated brain synchronization."""

    def resolve(self, local_data: Any, remote_data: Any) -> Any:
        """Resolve conflict between local and remote versioned payloads.

        Algorithm:
        - If local.version > remote.version: return local_data
        - If remote.version > local.version: return remote_data
        - If versions match: structural merge of payload dictionaries
        """
        local_v = getattr(local_data, "version", 1)
        remote_v = getattr(remote_data, "version", 1)

        if local_v > remote_v:
            return local_data
        elif remote_v > local_v:
            return remote_data
        else:
            return self.merge(local_data, remote_data)

    def merge(self, local_data: Any, remote_data: Any) -> Any:
        """Perform union merge of payload fields."""
        merged = copy.deepcopy(local_data)
        if hasattr(local_data, "payload") and hasattr(remote_data, "payload"):
            if isinstance(local_data.payload, dict) and isinstance(remote_data.payload, dict):
                merged.payload = {**local_data.payload, **remote_data.payload}
        return merged

