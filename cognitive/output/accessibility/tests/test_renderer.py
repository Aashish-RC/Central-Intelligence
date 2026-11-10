"""Unit tests for Accessible Output Renderer (Feature 6.34)."""

import pytest
from cognitive.output.accessibility.renderer import (
    AccessibleOutputRenderer,
    CaptionCue,
)


def test_generated_image_includes_alt_text_and_aria_attributes():
    renderer = AccessibleOutputRenderer()

    image_out = renderer.render_accessible_image(
        src="https://cdn.centralintelligence.io/charts/q3_roi.png",
        title="Q3 Mission ROI Overview",
        description="Bar chart showing a 45% reduction in cognitive latency and 99.9% uptime across all agents.",
        detected_elements=["bar chart", "latency metric", "uptime gauge"],
    )

    # Generated image includes alt text
    assert "Q3 Mission ROI Overview" in image_out.alt_text
    assert "45% reduction in cognitive latency" in image_out.alt_text

    # ARIA labels and semantic markup
    assert image_out.aria_label == "Image: Q3 Mission ROI Overview"
    assert 'role="img"' in image_out.html_markup
    assert 'alt="Q3 Mission ROI Overview.' in image_out.html_markup
    assert "<figcaption>Q3 Mission ROI Overview</figcaption>" in image_out.html_markup


def test_generated_audio_includes_captions_vtt_and_srt():
    renderer = AccessibleOutputRenderer()

    cues = [
        CaptionCue(
            start_time=0.0,
            end_time=3.5,
            text="Central Intelligence system boot sequence initiated.",
            speaker="Operator",
        ),
        CaptionCue(
            start_time=3.6,
            end_time=7.0,
            text="All neural nodes reports green status.",
            speaker="AI Assistant",
        ),
    ]

    audio_out = renderer.render_accessible_audio(
        audio_src="https://cdn.centralintelligence.io/audio/briefing_01.mp3",
        title="Daily Standup Briefing",
        cues=cues,
    )

    # WebVTT captions
    assert audio_out.vtt_captions.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:03.500" in audio_out.vtt_captions
    assert "<v Operator>Central Intelligence system boot sequence initiated." in audio_out.vtt_captions

    # SRT captions
    assert "00:00:03,600 --> 00:00:07,000" in audio_out.srt_captions
    assert "AI Assistant: All neural nodes reports green status." in audio_out.srt_captions

    # Screen reader transcript
    assert "[Operator]: Central Intelligence system boot sequence initiated." in audio_out.transcript_text

