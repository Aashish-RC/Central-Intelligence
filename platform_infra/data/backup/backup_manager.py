"""Automated Backup and Point-in-Time Recovery Manager across L15 Stores (L15 Feature 15.37)."""

from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class BackupSnapshot:
    """Point-in-time snapshot capturing state across registered stores."""

    backup_id: str
    created_at: float
    stores: Dict[str, Any]
    checksum: str
    label: str = ""


class BackupManager:
    """Coordinates full and point-in-time backups and restores across data stores."""

    def __init__(self) -> None:
        self._exporters: Dict[str, Callable[[], Any]] = {}
        self._restorers: Dict[str, Callable[[Any], None]] = {}
        self._snapshots: List[BackupSnapshot] = []

    def register_store(
        self,
        store_name: str,
        exporter: Callable[[], Any],
        restorer: Callable[[Any], None],
    ) -> None:
        self._exporters[store_name] = exporter
        self._restorers[store_name] = restorer

    def create_backup(
        self,
        label: str = "",
        timestamp: Optional[float] = None,
    ) -> BackupSnapshot:
        state = {name: copy.deepcopy(fn()) for name, fn in self._exporters.items()}
        serialized = json.dumps(state, sort_keys=True, default=str).encode("utf-8")
        snap = BackupSnapshot(
            backup_id=f"bkp-{uuid.uuid4().hex[:12]}",
            created_at=time.time() if timestamp is None else float(timestamp),
            stores=state,
            checksum=hashlib.sha256(serialized).hexdigest(),
            label=label,
        )
        self._snapshots.append(snap)
        self._snapshots.sort(key=lambda s: s.created_at)
        return snap

    def list_backups(self) -> List[BackupSnapshot]:
        return list(self._snapshots)

    def restore_backup(self, backup_id: str) -> BackupSnapshot:
        for snap in self._snapshots:
            if snap.backup_id == backup_id:
                for store_name, restorer in self._restorers.items():
                    if store_name in snap.stores:
                        restorer(copy.deepcopy(snap.stores[store_name]))
                return snap
        raise KeyError(f"Unknown backup_id '{backup_id}'")

    def restore_point_in_time(self, target_timestamp: float) -> BackupSnapshot:
        """Restore every registered store to the newest snapshot at or before ``target_timestamp``."""
        candidates = [s for s in self._snapshots if s.created_at <= target_timestamp]
        if not candidates:
            raise LookupError(f"No backup snapshot exists at or before {target_timestamp}")
        latest = candidates[-1]
        return self.restore_backup(latest.backup_id)

