"""
Unit tests for Situational Context Probe (Layer 1: Perception, Task 1.9).
"""

from datetime import datetime, timezone
import pytest
from cognitive.perception.situational.context_probe import (
    ProbeResult,
    SituationalContextProbe,
)
from control.context.situational.injector import SituationalContext, SituationalInjector


def test_probe_returns_all_required_fields():
    """
    Acceptance: Returns {date, time, tz, locale, device, activity}.
    """
    probe = SituationalContextProbe(default_tz="UTC")
    fixed_time = datetime(2026, 11, 10, 14, 30, 0, tzinfo=timezone.utc)

    result = probe.probe(current_time=fixed_time, active_window="Visual Studio Code - main.py")

    assert isinstance(result, ProbeResult)
    data = result.to_dict()

    # Exact key set assertion as defined in acceptance criteria
    expected_keys = {"date", "time", "tz", "locale", "device", "activity"}
    assert expected_keys.issubset(data.keys())

    assert data["date"] == "2026-11-10"
    assert "02:30:00 PM" in data["time"] or "2:30:00 PM" in data["time"]
    assert data["tz"] == "UTC"
    assert len(data["locale"]) > 0
    assert data["device"] in ("desktop", "laptop", "container", "mobile")
    assert data["activity"] == "coding"


def test_activity_inference_heuristics():
    """Verify activity categorization based on active application context."""
    probe = SituationalContextProbe()

    assert probe.infer_activity("Terminal - powershell.exe") == "terminal operations"
    assert probe.infer_activity("Google Chrome - Pull Request #42") == "browsing"
    assert probe.infer_activity("Slack - #incident-response") == "collaborating"
    assert probe.infer_activity("code editor - engine.ts") == "coding"
    assert probe.infer_activity(None) == "active user interaction"


def test_wire_into_l9_situational_injector():
    """Verify bidirectional wiring between L1 Context Probe and L9 SituationalInjector."""
    probe = SituationalContextProbe(default_tz="UTC")

    # Call probe.supply_to_l9
    ctx = probe.supply_to_l9(
        active_workspace="d:/central-intelligence",
        active_document="context_probe.py",
        active_window="Visual Studio Code",
    )

    assert isinstance(ctx, SituationalContext)
    assert ctx.active_workspace == "d:/central-intelligence"
    assert ctx.active_document == "context_probe.py"
    assert ctx.user_activity == "coding"

    # Call SituationalInjector.capture_from_probe
    ctx_from_l9 = SituationalInjector.capture_from_probe(
        probe=probe,
        active_workspace="d:/central-intelligence",
        active_window="Terminal",
    )
    assert ctx_from_l9.user_activity == "terminal operations"

    # Verify prompt formatting block
    block = SituationalInjector.format_block(ctx_from_l9)
    assert "- Current Time:" in block
    assert "- Active Workspace:" in block
    assert "Current User Activity: terminal operations" in block

