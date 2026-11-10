"""Unit tests for JanDesktopAdapter (Task 18.2)."""

import pytest
from surface.interaction.desktop.jan_adapter import (
    JanDesktopAdapter,
    DesktopAppState,
)


@pytest.fixture
def jan_app():
    return JanDesktopAdapter(privacy_mode=True)


def test_run_as_desktop_app_with_local_models(jan_app: JanDesktopAdapter):
    """Acceptance test: Can run as desktop app with local models."""
    # Launch app
    state = jan_app.launch()
    assert state == DesktopAppState.RUNNING

    # Load local model
    session = jan_app.load_local_model("llama-3.2-3b-instruct-q4")
    assert session.model_name == "llama-3.2-3b-instruct-q4"
    assert session.is_fully_offline is True

    # Run on-device local inference
    res = jan_app.run_local_inference("Explain memory hierarchy in modern CPU architectures")
    assert res["offline_executed"] is True
    assert "llama-3.2-3b-instruct-q4" in res["model"]
    assert len(res["response"]) > 0

    # Test window lifecycle
    assert jan_app.minimize_to_tray() == DesktopAppState.MINIMIZED
    assert jan_app.quit() == DesktopAppState.STOPPED
