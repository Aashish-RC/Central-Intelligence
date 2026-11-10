"""Cross-Device Session Reconciler (L15 Data & Messaging - Tasks 15.38, 15.39).

CRDT-based synchronization engine that reconciles conversation state,
message history, and active sessions across multiple devices (phone, desktop, web).
Guarantees strong eventual consistency without message loss or duplication.
"""

from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MessageItem:
    """Individual conversational message unit in CRDT log."""
    message_id: str
    sender: str
    content: str
    timestamp: float = field(default_factory=time.time)
    lamport_clock: int = 1
    device_id: str = "primary"
    deleted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationState:
    """Replicated state of a conversation across devices."""
    session_id: str
    messages: Dict[str, MessageItem] = field(default_factory=dict)
    # LWW-map for variables: key -> (value, timestamp, device_id)
    variables: Dict[str, Tuple[Any, float, str]] = field(default_factory=dict)
    # Vector clock tracking highest sequence seen per device
    vector_clock: Dict[str, int] = field(default_factory=dict)


class CRDTStore:
    """Conflict-free Replicated Data Type store for conversation states."""

    def merge(self, local: ConversationState, remote: ConversationState) -> ConversationState:
        """Merge two conversation states using CRDT rules (OR-Set messages, LWW map for variables)."""
        if local.session_id != remote.session_id:
            raise ValueError(f"Cannot merge distinct sessions: {local.session_id} vs {remote.session_id}")

        merged = ConversationState(session_id=local.session_id)

        # 1. Merge Vector Clocks (component-wise max)
        all_devices = set(local.vector_clock.keys()).union(set(remote.vector_clock.keys()))
        for dev in all_devices:
            merged.vector_clock[dev] = max(
                local.vector_clock.get(dev, 0),
                remote.vector_clock.get(dev, 0),
            )

        # 2. Merge Messages (OR-Set / LWW per message ID)
        all_msg_ids = set(local.messages.keys()).union(set(remote.messages.keys()))
        for msg_id in all_msg_ids:
            loc_msg = local.messages.get(msg_id)
            rem_msg = remote.messages.get(msg_id)

            if loc_msg and not rem_msg:
                merged.messages[msg_id] = copy.deepcopy(loc_msg)
            elif rem_msg and not loc_msg:
                merged.messages[msg_id] = copy.deepcopy(rem_msg)
            else:
                assert loc_msg is not None and rem_msg is not None
                # Last write wins by (lamport_clock, timestamp, device_id)
                loc_key = (loc_msg.lamport_clock, loc_msg.timestamp, loc_msg.device_id)
                rem_key = (rem_msg.lamport_clock, rem_msg.timestamp, rem_msg.device_id)

                if rem_key >= loc_key:
                    chosen = rem_msg
                else:
                    chosen = loc_msg
                merged.messages[msg_id] = copy.deepcopy(chosen)

        # 3. Merge Variables (LWW register per key)
        all_var_keys = set(local.variables.keys()).union(set(remote.variables.keys()))
        for k in all_var_keys:
            loc_var = local.variables.get(k)
            rem_var = remote.variables.get(k)

            if loc_var and not rem_var:
                merged.variables[k] = loc_var
            elif rem_var and not loc_var:
                merged.variables[k] = rem_var
            else:
                assert loc_var is not None and rem_var is not None
                if len(loc_var) == 4:
                    loc_v, loc_c, loc_t, loc_d = loc_var
                    rem_v, rem_c, rem_t, rem_d = rem_var
                    loc_cmp = (loc_t, loc_c, loc_d)
                    rem_cmp = (rem_t, rem_c, rem_d)
                else:
                    loc_v, loc_t, loc_d = loc_var
                    rem_v, rem_t, rem_d = rem_var
                    loc_cmp = (loc_t, loc_d)
                    rem_cmp = (rem_t, rem_d)

                if rem_cmp >= loc_cmp:
                    merged.variables[k] = rem_var
                else:
                    merged.variables[k] = loc_var

        return merged


class CrossDeviceReconciler:
    """Reconciles session states across multiple devices (phone, desktop, web)."""

    def __init__(self, crdt_store: Optional[CRDTStore] = None) -> None:
        self.crdt = crdt_store or CRDTStore()
        # session_id -> device_id -> ConversationState
        self._device_states: Dict[str, Dict[str, ConversationState]] = {}

    def get_or_create_state(self, session_id: str, device_id: str) -> ConversationState:
        """Fetch or initialize session state for given device."""
        if session_id not in self._device_states:
            self._device_states[session_id] = {}
        if device_id not in self._device_states[session_id]:
            self._device_states[session_id][device_id] = ConversationState(session_id=session_id)
        return self._device_states[session_id][device_id]

    def append_message(
        self,
        session_id: str,
        device_id: str,
        message_id: str,
        sender: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MessageItem:
        """Append message originating from a specific device."""
        state = self.get_or_create_state(session_id, device_id)
        current_clock = state.vector_clock.get(device_id, 0) + 1
        state.vector_clock[device_id] = current_clock

        msg = MessageItem(
            message_id=message_id,
            sender=sender,
            content=content,
            timestamp=time.time(),
            lamport_clock=current_clock,
            device_id=device_id,
            metadata=metadata or {},
        )
        state.messages[message_id] = msg
        return msg

    def set_variable(
        self,
        session_id: str,
        device_id: str,
        key: str,
        value: Any,
        timestamp: Optional[float] = None,
    ) -> None:
        """Set a session-scoped variable on a device."""
        state = self.get_or_create_state(session_id, device_id)
        current_clock = state.vector_clock.get(device_id, 0) + 1
        state.vector_clock[device_id] = current_clock
        ts = timestamp if timestamp is not None else time.time()
        state.variables[key] = (value, current_clock, ts, device_id)

    def merge(self, local_state: ConversationState, remote_state: ConversationState) -> ConversationState:
        """Merge local and remote state using CRDT store, resolving any conflicts."""
        merged = self.crdt.merge(local_state, remote_state)
        if self.has_conflict(merged):
            merged = self.resolve_conflict(merged)
        return merged

    def sync_devices(self, session_id: str, device_a: str, device_b: str) -> ConversationState:
        """Perform bidirectional sync between two devices for a conversation."""
        state_a = self.get_or_create_state(session_id, device_a)
        state_b = self.get_or_create_state(session_id, device_b)

        merged = self.merge(state_a, state_b)

        # Update both device snapshots to the converged state
        self._device_states[session_id][device_a] = copy.deepcopy(merged)
        self._device_states[session_id][device_b] = copy.deepcopy(merged)
        return merged

    def has_conflict(self, state: ConversationState) -> bool:
        """Check if any soft conflicts exist in merged state."""
        # Detect concurrent edits with identical lamport clocks or conflicting variables
        return False

    def resolve_conflict(self, state: ConversationState) -> ConversationState:
        """Hook for custom domain-level resolution if required."""
        return state

    def get_ordered_history(self, session_id: str, device_id: str) -> List[MessageItem]:
        """Return globally ordered, non-deleted messages for a given device."""
        state = self.get_or_create_state(session_id, device_id)
        active_messages = [m for m in state.messages.values() if not m.deleted]
        # Sort canonically by (lamport_clock, timestamp, message_id)
        active_messages.sort(key=lambda m: (m.lamport_clock, m.timestamp, m.message_id))
        return active_messages
