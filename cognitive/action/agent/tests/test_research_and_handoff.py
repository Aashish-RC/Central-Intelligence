"""Tests for L5 DeepResearchExecutor and AgentHandoffCoordinator."""

import pytest

from cognitive.action.agent.executor.agent_handoff import (
    AgentHandoffCoordinator,
    HandoffContextPackage,
)
from cognitive.action.agent.executor.deep_research import (
    DeepResearchExecutor,
    SourceDocument,
)


@pytest.mark.asyncio
async def test_deep_research_produces_cited_report():
    async def stub_search(subquery: str):
        return [
            SourceDocument(
                url="https://health.example.org/ai-triage",
                title="AI in Emergency Triage",
                content="AI triage models reduced ER wait times by 18% across three hospitals.",
            ),
            SourceDocument(
                url="https://radiology.example.org/screening",
                title="Radiology Screening Study",
                content="Computer-aided detection improved early nodule sensitivity while lowering false alarms.",
            ),
        ]

    executor = DeepResearchExecutor(search_fn=stub_search, max_iterations=2)
    report = await executor.research("impact of AI on healthcare")

    assert report.iterations_completed == 2
    assert len(report.sources) >= 2
    assert len(report.findings) >= 2
    assert "[1]" in report.report_markdown
    assert "## References" in report.report_markdown


@pytest.mark.asyncio
async def test_agent_to_agent_handoff_researcher_to_writer():
    coord = AgentHandoffCoordinator()

    async def writer_handler(pkg: HandoffContextPackage):
        assert pkg.source_agent == "researcher"
        assert "18% ER wait reduction" in pkg.findings
        return f"Draft Brief ({pkg.task}): " + "; ".join(pkg.findings)

    coord.register_agent("writer", writer_handler)

    res = await coord.handoff(
        HandoffContextPackage(
            source_agent="researcher",
            target_agent="writer",
            task="Write executive summary",
            conversation_summary="Completed literature review on hospital AI",
            findings=["18% ER wait reduction", "HIPAA audit compliant"],
            artifacts={"sources_count": 4},
        )
    )
    assert res.success is True
    assert "Draft Brief (Write executive summary)" in res.output
    assert res.provenance == ["researcher->writer"]

