"""
Zero-Knowledge Encrypted Relay Router.
Routes encrypted frames between endpoints without inspecting ciphertext.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from remote_access.core.device_registry import PairedDeviceRegistry
from remote_access.core.models import EncryptedFrame


class EncryptedRelayRouter:
    """Zero-knowledge message router forwarding encrypted frames between authorized devices."""

    def __init__(self, registry: Optional[PairedDeviceRegistry] = None):
        self.registry = registry or PairedDeviceRegistry()
        self._inbox: Dict[str, List[EncryptedFrame]] = {}  # recipient_id -> queue
        self.forwarded_count = 0
        self.forwarded_bytes = 0

    def route_frame(self, frame: EncryptedFrame) -> bool:
        """Inspects only sender and recipient headers, enqueuing frame for delivery."""
        # Check authorization
        if not self.registry.is_authorized(frame.sender_id):
            return False

        if not self.registry.is_authorized(frame.recipient_id):
            return False

        if frame.recipient_id not in self._inbox:
            self._inbox[frame.recipient_id] = []

        self._inbox[frame.recipient_id].append(frame)
        self.forwarded_count += 1
        self.forwarded_bytes += len(frame.ciphertext)
        return True

    def receive_frames(self, recipient_id: str) -> List[EncryptedFrame]:
        """Polls and drains queued encrypted frames for the specified recipient."""
        if not self.registry.is_authorized(recipient_id):
            return []

        frames = self._inbox.pop(recipient_id, [])
        return frames
