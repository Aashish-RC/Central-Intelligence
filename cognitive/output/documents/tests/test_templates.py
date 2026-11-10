"""Unit tests for Document Assembly Templates (Features 6.25 - 6.28)."""

import pytest
from cognitive.output.documents.template_engine import (
    DocumentTemplateEngine,
    ReportSection,
    DocumentType,
)


def test_can_generate_a_5_section_report_with_toc_from_a_template():
    engine = DocumentTemplateEngine()

    sections = [
        ReportSection(
            id="sec-1",
            title="Executive Summary",
            content="Central Intelligence successfully integrated Wave D Layers 6 and 7.",
            citations=["Vaswani et al. (2017)"],
        ),
        ReportSection(
            id="sec-2",
            title="Perception Architecture",
            content="Layer 1 handles LiveKit audio streams, Crawl4AI web extraction, and Screenpipe frames.",
        ),
        ReportSection(
            id="sec-3",
            title="Generative Output Pipelines",
            content="Layer 6 integrates CopilotKit generative UI, TipTap rich text, and Mermaid diagrams.",
            embedded_media={
                "type": "image",
                "url": "https://ci.internal/arch_diagram.png",
                "caption": "Layer 6 Output Generation Pipeline",
            },
        ),
        ReportSection(
            id="sec-4",
            title="Learning & Adaptation Loop",
            content="Layer 7 incorporates Cognee knowledge graphs, LangMem episodic memory, and Agenta workspaces.",
            citations=["LangChain AI (2024)", "Topoteretes (2024)"],
        ),
        ReportSection(
            id="sec-5",
            title="Future Milestones & Risk Assessment",
            content="Wave D Continue 2 will advance Data, Compute, and Release infrastructure.",
        ),
    ]

    doc = engine.build_report(
        title="Central Intelligence Operational Audit",
        sections=sections,
        author="Lead Intelligence Architect",
        doc_type=DocumentType.REPORT,
    )

    # 5 sections verification
    assert doc.sections_count == 5
    assert doc.citations_count == 3

    # Table of Contents verification
    assert "## Table of Contents" in doc.toc_markdown
    assert "[1.0 Executive Summary]" in doc.toc_markdown
    assert "[2.0 Perception Architecture]" in doc.toc_markdown
    assert "[3.0 Generative Output Pipelines]" in doc.toc_markdown
    assert "[4.0 Learning & Adaptation Loop]" in doc.toc_markdown
    assert "[5.0 Future Milestones & Risk Assessment]" in doc.toc_markdown
    assert "[References & Citations]" in doc.toc_markdown

    # Full document structure verification
    assert "# Central Intelligence Operational Audit" in doc.full_markdown
    assert "## <a id='10-executive-summary'></a>1.0 Executive Summary" in doc.full_markdown
    assert "![Layer 6 Output Generation Pipeline]" in doc.full_markdown
    assert "Vaswani et al. (2017)" in doc.full_markdown
