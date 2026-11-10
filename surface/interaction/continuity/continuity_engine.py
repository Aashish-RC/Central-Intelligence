"""Conversation Continuity Engine (L18 Interaction - Task 18.07).

Enables seamless conversation continuity across web, desktop, and mobile surfaces.
Wired directly with the L15 Cross-Device Reconciler CRDT synchronization layer.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from platform_infra.data.sync.cross_device_reconciler import (
    CrossDeviceReconciler,
    MessageItem,
)

logger = logging.getLogger(__name__)


@dataclass
class SurfaceSession:
    """Represents a client surface's active conversational view."""
    session_id: str
    surface_type: str  # "web", "desktop", "mobile", "terminal", "ide"
    last_read_message_id: Optional[str] = None
    active_draft: Optional[str] = None
    last_synced_at: float = field(default_factory=time.time)


class ConversationContinuityEngine:
    """Orchestrates seamless session handoffs between diverse interaction surfaces."""

    def __init__(self, reconciler: Optional[CrossDeviceReconciler] = None) -> None:
        self.reconciler = reconciler or CrossDeviceReconciler()
        # session_id -> surface_type -> SurfaceSession
        self._sessions: Dict[str, Dict[str, SurfaceSession]] = {}

    def _ensure_session(self, session_id: str, surface_type: str) -> SurfaceSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = {}
        if surface_type not in self._sessions[session_id]:
            self._sessions[session_id][surface_type] = SurfaceSession(
                session_id=session_id,
                surface_type=surface_type,
            )
        return self._sessions[session_id][surface_type]

    def post_turn(
        self,
        session_id: str,
        surface_type: str,
        message_id: str,
        sender: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MessageItem:
        """Record a conversation turn originating from a specific client surface."""
        self._ensure_session(session_id, surface_type)
        return self.reconciler.append_message(
            session_id=session_id,
            device_id=surface_type,
            message_id=message_id,
            sender=sender,
            content=content,
            metadata=metadata,
        )

    def set_draft(self, session_id: str, surface_type: str, draft_text: str) -> None:
        """Persist in-progress user draft on surface with LWW CRDT propagation."""
        session = self._ensure_session(session_id, surface_type)
        session.active_draft = draft_text
        self.reconciler.set_variable(session_id, surface_type, "active_draft", draft_text)

    def handoff_session(
        self,
        session_id: str,
        from_surface: str,
        to_surface: str,
    ) -> List[MessageItem]:
        """Perform seamless surface handoff; syncs CRDT state and returns full history."""
        # Bidirectional sync between the source surface and destination surface
        converged_state = self.reconciler.sync_devices(
            session_id=session_id,
            device_a=from_surface,
            device_b=to_surface,
        )

        dest_session = self._ensure_session(session_id, to_surface)
        dest_session.last_synced_at = time.time()

        # Reconcile active draft if available
        if "active_draft" in converged_state.variables:
            dest_session.active_draft = converged_state.variables["active_draft"][0]

        history = self.reconciler.get_ordered_history(session_id, to_surface)
        if history:
            dest_session.last_read_message_id = history[-1].message_id

        logger.info(
            "Handoff session '%s' from %s to %s complete: %d messages synced",
            session_id,
            from_surface,
            to_surface,
            len(history),
        )
        return history

    def get_surface_draft(self, session_id: str, surface_type: str) -> Optional[str]:
        """Get active draft for surface."""
        session = self._ensure_session(session_id, surface_type)
        return session.active_draft

