"""Federated Brain Synchronization protocol crown jewel (L19 Federation)."""

from .consent_gate import ConsentGate, ConsentDeniedError
from .conflict_resolver import BrainConflictResolver
from .federated_sync import (
    FederatedBrainSync,
    FederatedDataPayload,
    EncryptedEnvelope,
)

__all__ = [
    "ConsentGate",
    "ConsentDeniedError",
    "BrainConflictResolver",
    "FederatedBrainSync",
    "FederatedDataPayload",
    "EncryptedEnvelope",
]
