"""Unit tests for CrossAppMemorySharing (Task 19.5)."""

import pytest
from surface.federation.memory.cross_app_sharing import (
    CrossAppMemorySharing,
    MemoryClassification,
)


@pytest.fixture
def sharing():
    return CrossAppMemorySharing()


def test_app_a_can_access_preferences_but_not_app_b_private_content(sharing: CrossAppMemorySharing):
    """Acceptance test: App A can access user preferences but not App B's private content."""
    app_a = "app_analytics_dashboard"
    app_b = "app_confidential_legal_docs"

    # App B records a universal user preference
    pref_item = sharing.store_memory(
        owner_app_id=app_b,
        classification=MemoryClassification.USER_PREFERENCE,
        key="ui_theme",
        value="dark_slate",
        tags=["preference", "ui"],
    )

    # App B records private content behind its data wall
    private_item = sharing.store_memory(
        owner_app_id=app_b,
        classification=MemoryClassification.APP_PRIVATE_CONTENT,
        key="merger_valuation_secrets",
        value={"acquirer": "CorpX", "bid_millions": 450},
        tags=["confidential", "m&a"],
    )

    # 1. App A can access the preference stored by App B
    fetched_pref = sharing.get_memory(requester_app_id=app_a, memory_id=pref_item.memory_id)
    assert fetched_pref.value == "dark_slate"

    # 2. App A is blocked from accessing App B's private content
    with pytest.raises(PermissionError, match="Data Wall Violation"):
        sharing.get_memory(requester_app_id=app_a, memory_id=private_item.memory_id)

    # 3. Ecosystem search by App A returns preference but hides private content
    results = sharing.search_ecosystem_memory(requester_app_id=app_a)
    result_keys = {item.key for item in results}
    assert "ui_theme" in result_keys
    assert "merger_valuation_secrets" not in result_keys

    # 4. App B can access its own private content freely
    app_b_access = sharing.get_memory(requester_app_id=app_b, memory_id=private_item.memory_id)
    assert app_b_access.value["bid_millions"] == 450
