"""Unit tests for UniversalSurfaceAdapter Crown Jewel (Task 18.5)."""

import pytest
from surface.interaction.universal.surface_adapter import (
    UniversalSurfaceAdapter,
    SurfaceType,
    ContentBlock,
    NormalizedEvent,
)


@pytest.fixture
def universal():
    return UniversalSurfaceAdapter()


def test_same_ai_response_renders_across_all_surfaces(universal: UniversalSurfaceAdapter):
    """Acceptance test: Same AI response renders correctly on web, desktop, terminal, and IDE."""
    code_block = ContentBlock(
        block_type="code",
        content="def calculate_total(items):\n    return sum(items)",
        metadata={"language": "python"},
    )

    # 1. Web renders HTML <pre><code class="language-python">
    web_rendered = universal.render(code_block, surface_type=SurfaceType.WEB)
    assert isinstance(web_rendered, str)
    assert "<pre><code class='language-python'>" in web_rendered
    assert "calculate_total" in web_rendered

    # 2. Desktop renders native structured payload
    desktop_rendered = universal.render(code_block, surface_type=SurfaceType.DESKTOP)
    assert isinstance(desktop_rendered, dict)
    assert desktop_rendered["surface"] == "desktop"
    assert desktop_rendered["component"] == "NativeRichView"
    assert "calculate_total" in desktop_rendered["body"]

    # 3. Terminal renders ANSI styled block
    term_rendered = universal.render(code_block, surface_type=SurfaceType.TERMINAL)
    assert isinstance(term_rendered, str)
    assert "\x1b[32m" in term_rendered  # Green ANSI text
    assert "calculate_total" in term_rendered

    # 4. IDE renders markdown code fence format
    ide_rendered = universal.render(code_block, surface_type=SurfaceType.IDE)
    assert isinstance(ide_rendered, dict)
    assert ide_rendered["surface"] == "ide"
    assert "```python\ndef calculate_total" in ide_rendered["content"]


def test_generative_ui_button_rendering(universal: UniversalSurfaceAdapter):
    """Button block renders with click handler on web, native button on desktop, and key prompt on CLI."""
    btn = ContentBlock(
        block_type="button",
        content="Deploy to Production",
        metadata={"action": "deploy_prod"},
    )

    web_btn = universal.render(btn, "web")
    assert "<button class='ai-action-btn' data-action='deploy_prod'>Deploy to Production</button>" in web_btn

    term_btn = universal.render(btn, "terminal")
    assert "[Button: Deploy to Production (Press Enter to execute)]" in term_btn


def test_streaming_event_normalization(universal: UniversalSurfaceAdapter):
    """Normalized stream delivery across web SSE, desktop IPC, terminal, and IDE LSP."""
    event = NormalizedEvent(event_type="token", payload="Hello world")

    web_stream = universal.stream(event, "web")
    assert "data: " in web_stream

    term_stream = universal.stream(event, "terminal")
    assert "[stream]" in term_stream
    assert "Hello world" in term_stream

    ide_stream = universal.stream(event, "ide")
    assert ide_stream["lsp_notification"] == "zed/streamEvent"


def test_confirmation_across_surfaces(universal: UniversalSurfaceAdapter):
    """Tool confirmation works uniformly across all 4 surfaces."""
    for surface in ["web", "desktop", "terminal", "ide"]:
        confirmed = universal.confirm("execute_db_migration", surface_type=surface)
        assert confirmed is True
