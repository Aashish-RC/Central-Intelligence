"""Shared state and concurrency coordination layer for multi-agent action execution."""

from .lock_manager import (
    DistributedLockManager,
    LockAcquisitionError,
    LockLease,
    LockMode,
)
from .scratchpad import (
    SharedScratchpad,
    ScratchpadEntry,
    ScratchpadMutationAudit,
)

ScratchpadTransaction = ScratchpadMutationAudit

__all__ = [
    "DistributedLockManager",
    "LockAcquisitionError",
    "LockLease",
    "LockMode",
    "SharedScratchpad",
    "ScratchpadEntry",
    "ScratchpadMutationAudit",
    "ScratchpadTransaction",
]
