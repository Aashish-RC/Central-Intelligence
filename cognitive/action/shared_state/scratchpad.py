"""Shared Scratchpad: Collaborative working blackboard for concurrent agents.

Provides thread-safe and lock-governed key-value working memory, atomic
mutations (compare-and-set, atomic increment), and full revision audit trails.

Features: 5.44, 5.45, 8.49
"""

from dataclasses import dataclass, field
import threading
import time
from typing import Any, Dict, List, Optional
from .lock_manager import DistributedLockManager, LockMode


@dataclass
class ScratchpadEntry:
    """An entry stored in the collaborative scratchpad."""
    key: str
    value: Any
    version: int
    last_modified_by: str
    updated_at: float = field(default_factory=time.time)


@dataclass
class ScratchpadMutationAudit:
    """Audit trail record of a scratchpad mutation."""
    key: str
    old_version: int
    new_version: int
    modified_by: str
    action: str
    timestamp: float = field(default_factory=time.time)


class SharedScratchpad:
    """Synchronized working memory blackboard shared across executing agents."""

    def __init__(
        self,
        namespace: str = "default",
        lock_manager: Optional[DistributedLockManager] = None,
    ):
        self.namespace = namespace
        self.lock_manager = lock_manager or DistributedLockManager()
        self._mutex = threading.RLock()
        self._storage: Dict[str, ScratchpadEntry] = {}
        self._audit_log: List[ScratchpadMutationAudit] = []

    def _lock_key(self, key: str) -> str:
        return f"scratchpad:{self.namespace}:{key}"

    def set(self, key: str, value: Any, agent_id: str) -> ScratchpadEntry:
        """Sets a value with mutual exclusion and auto-increments version."""
        lock_key = self._lock_key(key)
        with self.lock_manager.lock(lock_key, owner=agent_id, mode=LockMode.EXCLUSIVE):
            with self._mutex:
                old_entry = self._storage.get(key)
                old_ver = old_entry.version if old_entry else 0
                new_ver = old_ver + 1

                entry = ScratchpadEntry(
                    key=key,
                    value=value,
                    version=new_ver,
                    last_modified_by=agent_id,
                    updated_at=time.time(),
                )
                self._storage[key] = entry
                self._audit_log.append(
                    ScratchpadMutationAudit(
                        key=key,
                        old_version=old_ver,
                        new_version=new_ver,
                        modified_by=agent_id,
                        action="set",
                    )
                )
                return entry

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves value associated with key, returning default if absent."""
        with self._mutex:
            entry = self._storage.get(key)
            return entry.value if entry else default

    def get_entry(self, key: str) -> Optional[ScratchpadEntry]:
        """Retrieves the full ScratchpadEntry including version and author metadata."""
        with self._mutex:
            return self._storage.get(key)

    def delete(self, key: str, agent_id: str) -> bool:
        """Deletes key from scratchpad under lock protection."""
        lock_key = self._lock_key(key)
        with self.lock_manager.lock(lock_key, owner=agent_id, mode=LockMode.EXCLUSIVE):
            with self._mutex:
                if key in self._storage:
                    old_ver = self._storage[key].version
                    del self._storage[key]
                    self._audit_log.append(
                        ScratchpadMutationAudit(
                            key=key,
                            old_version=old_ver,
                            new_version=old_ver + 1,
                            modified_by=agent_id,
                            action="delete",
                        )
                    )
                    return True
                return False

    def compare_and_set(
        self,
        key: str,
        expected_version: int,
        new_value: Any,
        agent_id: str,
    ) -> bool:
        """Atomic Compare-and-Set (CAS): updates value only if current version matches expected."""
        lock_key = self._lock_key(key)
        with self.lock_manager.lock(lock_key, owner=agent_id, mode=LockMode.EXCLUSIVE):
            with self._mutex:
                current_entry = self._storage.get(key)
                current_ver = current_entry.version if current_entry else 0

                if current_ver != expected_version:
                    return False

                new_ver = current_ver + 1
                entry = ScratchpadEntry(
                    key=key,
                    value=new_value,
                    version=new_ver,
                    last_modified_by=agent_id,
                    updated_at=time.time(),
                )
                self._storage[key] = entry
                self._audit_log.append(
                    ScratchpadMutationAudit(
                        key=key,
                        old_version=current_ver,
                        new_version=new_ver,
                        modified_by=agent_id,
                        action="cas",
                    )
                )
                return True

    def atomic_increment(self, key: str, delta: int = 1, agent_id: str = "system") -> int:
        """Atomically increments an integer counter."""
        lock_key = self._lock_key(key)
        with self.lock_manager.lock(lock_key, owner=agent_id, mode=LockMode.EXCLUSIVE):
            with self._mutex:
                current_val = self.get(key, 0)
                if not isinstance(current_val, (int, float)):
                    raise TypeError(f"Key '{key}' holds non-numeric type {type(current_val)}")

                new_val = int(current_val + delta)
                self.set(key, new_val, agent_id=agent_id)
                return new_val

    def append_list(self, key: str, item: Any, agent_id: str) -> List[Any]:
        """Atomically appends an item to a list."""
        lock_key = self._lock_key(key)
        with self.lock_manager.lock(lock_key, owner=agent_id, mode=LockMode.EXCLUSIVE):
            with self._mutex:
                current_list = self.get(key, [])
                if not isinstance(current_list, list):
                    raise TypeError(f"Key '{key}' holds non-list type {type(current_list)}")

                new_list = list(current_list) + [item]
                self.set(key, new_list, agent_id=agent_id)
                return new_list

    def get_audit_history(self, limit: int = 50) -> List[ScratchpadMutationAudit]:
        """Returns the most recent mutation audit entries."""
        with self._mutex:
            return list(self._audit_log[-limit:])

    def clear(self) -> None:
        """Clears all stored entries and audit history."""
        with self._mutex:
            self._storage.clear()
            self._audit_log.clear()
