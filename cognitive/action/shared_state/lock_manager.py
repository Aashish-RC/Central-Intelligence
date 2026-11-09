"""Distributed Lock Manager: Concurrency control and lease management for multi-agent workflows.

Prevents race conditions, resource contention, and deadlocks across concurrent
agents operating on shared files, environments, or memory buffers.

Features: 5.44, 5.45, 8.49
"""

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import threading
import time
from typing import Dict, Generator, List, Optional, Set


class LockMode(str, Enum):
    """Concurrency lock mode."""
    EXCLUSIVE = "exclusive"  # Single writer lock
    SHARED = "shared"        # Multiple reader lock


class LockAcquisitionError(TimeoutError):
    """Raised when lock acquisition fails within the specified timeout window."""
    pass


@dataclass
class LockLease:
    """Active lease token granted to an owner."""
    key: str
    owner: str
    mode: LockMode
    acquired_at: float
    expires_at: float
    reentrancy_count: int = 1

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class DistributedLockManager:
    """Manages distributed mutexes and shared reader/writer locks with lease TTLs."""

    def __init__(self, default_ttl_seconds: float = 30.0):
        self.default_ttl = default_ttl_seconds
        self._mutex = threading.RLock()
        # key -> LockLease for exclusive locks
        self._exclusive_locks: Dict[str, LockLease] = {}
        # key -> Dict[owner, LockLease] for shared locks
        self._shared_locks: Dict[str, Dict[str, LockLease]] = {}

    def _purge_expired(self, key: str) -> None:
        """Internal helper to automatically expire abandoned leases."""
        now = time.time()
        if key in self._exclusive_locks:
            if self._exclusive_locks[key].expires_at < now:
                del self._exclusive_locks[key]

        if key in self._shared_locks:
            expired_owners = [
                owner for owner, lease in self._shared_locks[key].items()
                if lease.expires_at < now
            ]
            for owner in expired_owners:
                del self._shared_locks[key][owner]
            if not self._shared_locks[key]:
                del self._shared_locks[key]

    def acquire(
        self,
        key: str,
        owner: str,
        mode: LockMode = LockMode.EXCLUSIVE,
        ttl_seconds: Optional[float] = None,
        timeout: float = 0.0,
    ) -> LockLease:
        """Acquires a lock lease, waiting up to `timeout` seconds before raising LockAcquisitionError."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        deadline = time.time() + max(0.0, timeout)
        poll_interval = 0.05

        while True:
            with self._mutex:
                self._purge_expired(key)

                if mode == LockMode.EXCLUSIVE:
                    # Check if already held by this owner (reentrancy)
                    if key in self._exclusive_locks and self._exclusive_locks[key].owner == owner:
                        lease = self._exclusive_locks[key]
                        lease.reentrancy_count += 1
                        lease.expires_at = time.time() + ttl
                        return lease

                    # Check if no active exclusive or shared locks exist
                    if key not in self._exclusive_locks and key not in self._shared_locks:
                        now = time.time()
                        lease = LockLease(
                            key=key,
                            owner=owner,
                            mode=LockMode.EXCLUSIVE,
                            acquired_at=now,
                            expires_at=now + ttl,
                        )
                        self._exclusive_locks[key] = lease
                        return lease

                elif mode == LockMode.SHARED:
                    # Can acquire shared lock if no exclusive lock is active (or exclusive lock held by same owner)
                    is_exclusive_held = (
                        key in self._exclusive_locks and self._exclusive_locks[key].owner != owner
                    )
                    if not is_exclusive_held:
                        now = time.time()
                        if key not in self._shared_locks:
                            self._shared_locks[key] = {}

                        if owner in self._shared_locks[key]:
                            lease = self._shared_locks[key][owner]
                            lease.reentrancy_count += 1
                            lease.expires_at = now + ttl
                            return lease

                        lease = LockLease(
                            key=key,
                            owner=owner,
                            mode=LockMode.SHARED,
                            acquired_at=now,
                            expires_at=now + ttl,
                        )
                        self._shared_locks[key][owner] = lease
                        return lease

            if time.time() >= deadline:
                raise LockAcquisitionError(
                    f"Failed to acquire {mode.value} lock on '{key}' for owner '{owner}' within {timeout}s timeout"
                )

            time.sleep(poll_interval)

    def release(self, key: str, owner: str) -> bool:
        """Releases the lock held by the specified owner. Returns True if released."""
        with self._mutex:
            self._purge_expired(key)

            # Exclusive lock release
            if key in self._exclusive_locks:
                lease = self._exclusive_locks[key]
                if lease.owner == owner:
                    lease.reentrancy_count -= 1
                    if lease.reentrancy_count <= 0:
                        del self._exclusive_locks[key]
                    return True
                return False

            # Shared lock release
            if key in self._shared_locks and owner in self._shared_locks[key]:
                lease = self._shared_locks[key][owner]
                lease.reentrancy_count -= 1
                if lease.reentrancy_count <= 0:
                    del self._shared_locks[key][owner]
                if not self._shared_locks[key]:
                    del self._shared_locks[key]
                return True

            return False

    def extend_lease(self, key: str, owner: str, additional_ttl_seconds: float) -> bool:
        """Heartbeat/renewal: extends an active lease duration."""
        with self._mutex:
            self._purge_expired(key)

            if key in self._exclusive_locks and self._exclusive_locks[key].owner == owner:
                self._exclusive_locks[key].expires_at += additional_ttl_seconds
                return True

            if key in self._shared_locks and owner in self._shared_locks[key]:
                self._shared_locks[key][owner].expires_at += additional_ttl_seconds
                return True

            return False

    def is_locked(self, key: str) -> bool:
        """Check if a key is currently locked under any active non-expired lease."""
        with self._mutex:
            self._purge_expired(key)
            return key in self._exclusive_locks or key in self._shared_locks

    def get_owner(self, key: str) -> Optional[str]:
        """Returns the current exclusive owner, or first shared owner."""
        with self._mutex:
            self._purge_expired(key)
            if key in self._exclusive_locks:
                return self._exclusive_locks[key].owner
            if key in self._shared_locks and self._shared_locks[key]:
                return next(iter(self._shared_locks[key].keys()))
            return None

    @contextmanager
    def lock(
        self,
        key: str,
        owner: str,
        mode: LockMode = LockMode.EXCLUSIVE,
        ttl_seconds: Optional[float] = None,
        timeout: float = 0.0,
    ) -> Generator[LockLease, None, None]:
        """Context manager for RAII-style scoped locking."""
        lease = self.acquire(key, owner, mode=mode, ttl_seconds=ttl_seconds, timeout=timeout)
        try:
            yield lease
        finally:
            self.release(key, owner)
