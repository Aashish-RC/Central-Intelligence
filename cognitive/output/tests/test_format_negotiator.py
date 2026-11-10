"""Unit tests for Output Format Negotiator (Feature 6.35)."""

import pytest
from cognitive.output.format_negotiator import (
    OutputFormatNegotiator,
    ContentPayload,
    TargetSurface,
)


def test_same_content_produces_different_format_for_mobile_vs_web_vs_cli():
    negotiator = OutputFormatNegotiator()

    payload = ContentPayload(
        title="Deployment Report",
        body="All 12 microservices transitioned to healthy status after canary deployment.",
        summary="Canary deployment succeeded with 0 errors.",
        bullet_points=[
            "Latency P99 dropped by 18%",
            "Memory usage stabilized at 42%",
            "Zero HTTP 500 status codes observed",
        ],
        code_snippets=[{"language": "bash", "code": "kubectl get pods -n prod"}],
    )

    out_cli = negotiator.negotiate(payload, TargetSurface.CLI)
    out_web = negotiator.negotiate(payload, TargetSurface.WEB)
    out_mobile = negotiator.negotiate(payload, TargetSurface.MOBILE)
    out_email = negotiator.negotiate(payload, TargetSurface.EMAIL)

    # Verify all formats are distinct
    assert out_cli.format_type == "ansi_text"
    assert "\033[1;36m" in out_cli.formatted_content

    assert out_web.format_type == "rich_markdown"
    assert "# Deployment Report" in out_web.formatted_content
    assert "```bash" in out_web.formatted_content

    assert out_mobile.format_type == "mobile_markdown"
    assert "### 📱 Deployment Report" in out_mobile.formatted_content
    assert "Quick Take" in out_mobile.formatted_content

    assert out_email.format_type == "email_html"
    assert "<div style=" in out_email.formatted_content
    assert "<h1 style=" in out_email.formatted_content

    # Pairwise inequality of content
    contents = [
        out_cli.formatted_content,
        out_web.formatted_content,
        out_mobile.formatted_content,
        out_email.formatted_content,
    ]
    assert len(set(contents)) == 4


def test_voice_surface_negotiation():
    negotiator = OutputFormatNegotiator()
    payload = ContentPayload(
        title="Weather Alert",
        body="High winds expected in the northern sector.",
        bullet_points=["Stay indoors", "Secure loose gear"],
    )

    out_voice = negotiator.negotiate(payload, TargetSurface.VOICE)
    assert out_voice.format_type == "ssml_text"
    assert out_voice.formatted_content.startswith("<speak>")
    assert out_voice.formatted_content.endswith("</speak>")

