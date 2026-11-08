"""Custom exception definitions for the Memory Layer."""


class MemoryLayerError(Exception):
    """Base exception for all memory layer errors."""
    pass


class RecordNotFoundError(MemoryLayerError):
    """Raised when an expected memory record or fact is not found."""
    pass


class ContradictionResolutionError(MemoryLayerError):
    """Raised when contradiction resolution encounters an unresolvable conflict."""
    pass


class AdapterConnectionError(MemoryLayerError):
    """Raised when a storage adapter fails to establish or maintain connection."""
    pass


class TokenBudgetExceededError(MemoryLayerError):
    """Raised when synthesis strictly exceeds hard token allocations."""
    pass


class EmbeddingError(MemoryLayerError):
    """Raised when vector embedding generation fails."""
    pass
