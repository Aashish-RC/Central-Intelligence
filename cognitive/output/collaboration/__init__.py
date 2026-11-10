"""Real-time co-editing and conflict resolution (Feature 6.38)."""

from cognitive.output.collaboration.conflict_resolver import (
    ConflictResolver,
    TextOperation,
    OpType,
)

__all__ = ["ConflictResolver", "TextOperation", "OpType"]
