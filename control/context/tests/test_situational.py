"""Unit tests for Situational Context Injector (Task 9.7, Feature 9.16)."""

from datetime import datetime, timezone
import pytest
from control.context.situational.injector import SituationalInjector, SituationalContext
from control.context.assembly.context_assembler import ContextAssembler


def test_situational_datetime_and_platform_capture_acceptance():
    """Task 9.7 Acceptance:
    Model response includes awareness of current time ("It's 3:45 PM on November 9, 2026").
    """
    fixed_dt = datetime(2026, 11, 9, 15, 45, tzinfo=timezone.utc)
    ctx = SituationalInjector.capture(
        dt=fixed_dt,
        tz_name="UTC",
        locale="en-US",
        device_type="desktop",
        platform="windows",
        active_workspace="d:/central-intelligence",
        active_document="cognitive/memory/consolidation/decay_policy.py",
        user_activity="implementing Layer 9 context engineering",
    )

    assert "3:45 PM on November 9, 2026" in ctx.formatted_datetime
    assert ctx.platform == "windows"
    assert ctx.locale == "en-US"

    block = SituationalInjector.format_block(ctx)
    assert "- Current Time: 3:45 PM on November 9, 2026 (UTC)" in block
    assert "- Client Environment: windows (desktop)" in block
    assert "- Open Document: cognitive/memory/consolidation/decay_policy.py" in block
    assert "- Current User Activity: implementing Layer 9 context engineering" in block

    # Verify assembly with situational injector
    assembler = ContextAssembler()
    result = assembler.assemble(
        system_instructions="You are Aevum Core Brain.",
        situational_context=block,
        user_input="What time is it and what am I working on?",
    )

    assert "3:45 PM on November 9, 2026" in result.full_prompt
    assert "decay_policy.py" in result.full_prompt
    assert "<situational_context>" in result.full_prompt
