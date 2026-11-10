"""
Unit tests for Screenpipe Screen Awareness Adapter (Layer 1: Perception, Task 1.4).
"""

import time
import pytest
from cognitive.perception.screen.screenpipe_adapter import (
    OCRFrame,
    ScreenpipeAdapter,
)


@pytest.fixture
def timeline_adapter() -> tuple[ScreenpipeAdapter, float]:
    """Builds a timeline of OCR screen captures centered around a fixed now."""
    adapter = ScreenpipeAdapter()
    now = 1700000000.0  # reference time

    # Frame 1: 15 minutes ago (900s)
    adapter.record_frame(
        text="Terminal: git status on central-intelligence branch main",
        app_name="Terminal",
        window_title="bash - central-intelligence",
        timestamp=now - 900,
    )

    # Frame 2: 5 minutes ago (300s) - Target for acceptance test
    adapter.record_frame(
        text="VS Code: def calculate_risk_score(user_id): return 0.05",
        app_name="Visual Studio Code",
        window_title="risk_engine.py - central-intelligence",
        timestamp=now - 300,
    )

    # Frame 3: 1 minute ago (60s)
    adapter.record_frame(
        text="Chrome: Reviewing GitHub PR #42 on Central-Intelligence",
        app_name="Google Chrome",
        window_title="GitHub - Pull Request #42",
        timestamp=now - 60,
    )

    # Frame 4: Current moment (0s)
    adapter.record_frame(
        text="Slack: Deployment approved by SecOps Lead",
        app_name="Slack",
        window_title="#general - Central Intelligence",
        timestamp=now,
    )

    return adapter, now


def test_what_was_on_screen_5_minutes_ago(timeline_adapter):
    """
    Acceptance: Can query "what was on screen 5 minutes ago" and get OCR text.
    """
    adapter, now = timeline_adapter

    # Query specifically for 5 minutes ago (300 seconds ago)
    results = adapter.what_was_on_screen(seconds_ago=300.0, current_time=now)

    assert len(results) >= 1
    target_frame = results[0]
    assert isinstance(target_frame, OCRFrame)
    assert target_frame.app_name == "Visual Studio Code"
    assert "def calculate_risk_score(user_id): return 0.05" in target_frame.text
    assert target_frame.timestamp == now - 300


def test_query_screen_by_application(timeline_adapter):
    """Verify filtering OCR frames by active application."""
    adapter, now = timeline_adapter

    chrome_frames = adapter.query_screen(app_name="Google Chrome")
    assert len(chrome_frames) == 1
    assert "GitHub - Pull Request #42" in chrome_frames[0].window_title

    terminal_frames = adapter.query_screen(app_name="Terminal")
    assert len(terminal_frames) == 1
    assert "git status" in terminal_frames[0].text


def test_query_screen_keyword_search(timeline_adapter):
    """Verify semantic keyword search across historical OCR text."""
    adapter, now = timeline_adapter

    results = adapter.query_screen(query_text="Deployment approved")
    assert len(results) == 1
    assert results[0].app_name == "Slack"
    assert "SecOps Lead" in results[0].text


def test_fallback_to_closest_past_frame(timeline_adapter):
    """Verify fallback when an exact second timestamp is slightly offset."""
    adapter, now = timeline_adapter

    # Query 4 minutes ago (240s) where no frame exists in 20s tolerance
    results = adapter.what_was_on_screen(seconds_ago=240.0, tolerance_seconds=20.0, current_time=now)
    assert len(results) >= 1
    # Should resolve to the closest past frame (the 5 min ago frame)
    assert "calculate_risk_score" in results[0].text
