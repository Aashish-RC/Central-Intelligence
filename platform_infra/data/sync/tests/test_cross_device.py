"""Unit tests for CrossDeviceReconciler (Task 15.4)."""

import pytest
from platform_infra.data.sync.cross_device_reconciler import (
    CrossDeviceReconciler,
    CRDTStore,
    ConversationState,
    MessageItem,
)


@pytest.fixture
def reconciler():
    return CrossDeviceReconciler()


def test_cross_device_handoff_phone_to_desktop(reconciler: CrossDeviceReconciler):
    """Test switching phone -> desktop mid-conversation; full history is visible."""
    session_id = "sess_multi_dev_001"
    phone = "iphone_15"
    desktop = "macbook_pro"

    # User starts on phone
    reconciler.append_message(session_id, phone, "msg_1", "user", "Draft an email to the team")
    reconciler.append_message(session_id, phone, "msg_2", "assistant", "Sure, what is the key subject?")

    phone_history = reconciler.get_ordered_history(session_id, phone)
    assert len(phone_history) == 2

    # Desktop opens and has no messages yet
    desktop_history_before = reconciler.get_ordered_history(session_id, desktop)
    assert len(desktop_history_before) == 0

    # Sync phone <-> desktop
    reconciler.sync_devices(session_id, phone, desktop)

    # Full history is now present on desktop
    desktop_history_after = reconciler.get_ordered_history(session_id, desktop)
    assert len(desktop_history_after) == 2
    assert [m.message_id for m in desktop_history_after] == ["msg_1", "msg_2"]
    assert desktop_history_after[0].content == "Draft an email to the team"
    assert desktop_history_after[1].content == "Sure, what is the key subject?"


def test_concurrent_edits_across_devices(reconciler: CrossDeviceReconciler):
    """Test concurrent message additions on phone and desktop converge without loss."""
    session_id = "sess_concurrent_002"
    phone = "pixel_8"
    desktop = "workstation_linux"

    # Seed common base
    reconciler.append_message(session_id, phone, "msg_base", "user", "Hello world")
    reconciler.sync_devices(session_id, phone, desktop)

    # Concurrent edits while offline/disconnected
    reconciler.append_message(session_id, phone, "msg_phone_1", "user", "Sent from mobile commute")
    reconciler.append_message(session_id, desktop, "msg_desk_1", "user", "Sent from desk office")

    # Sync
    converged = reconciler.sync_devices(session_id, phone, desktop)

    phone_history = reconciler.get_ordered_history(session_id, phone)
    desk_history = reconciler.get_ordered_history(session_id, desktop)

    assert len(phone_history) == 3
    assert len(desk_history) == 3

    phone_ids = {m.message_id for m in phone_history}
    desk_ids = {m.message_id for m in desk_history}
    assert phone_ids == {"msg_base", "msg_phone_1", "msg_desk_1"}
    assert desk_ids == phone_ids


def test_variable_reconciliation_last_write_wins(reconciler: CrossDeviceReconciler):
    """Test session variables reconcile via LWW."""
    session_id = "sess_vars_003"
    phone = "phone"
    desktop = "desktop"

    reconciler.set_variable(session_id, phone, "theme", "dark", timestamp=100.0)
    reconciler.set_variable(session_id, desktop, "theme", "light", timestamp=200.0)

    converged = reconciler.sync_devices(session_id, phone, desktop)
    # The later write (desktop) wins
    assert converged.variables["theme"][0] == "light"
