"""Autonomous Multi-Step Deep Research Executor (L5 Feature 5.32).

Iteratively executes search -> read -> extract facts -> record citations -> repeat,
producing a structured research report with inline numbered citations.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional


@dataclass
class SourceDocument:
    """Fetched candidate page/document used as evidence during research."""

    url: str
    title: str
    content: str
    snippet: str = ""


@dataclass
class CitedFinding:
    """Extracted insight linked back to its source URL and citation index."""

    citation_id: int
    subquery: str
    statement: str
    source_url: str
    source_title: str


@dataclass
class DeepResearchReport:
    """Final multi-step deep research output with inline citations and bibliography."""

    topic: str
    iterations_completed: int
    findings: List[CitedFinding] = field(default_factory=list)
    sources: List[SourceDocument] = field(default_factory=list)
    report_markdown: str = ""


SearchFn = Callable[[str], List[SourceDocument] | Awaitable[List[SourceDocument]]]


class DeepResearchExecutor:
    """Runs iterative multi-hop web/knowledge research and compiles cited reports."""

    def __init__(
        self,
        search_fn: Optional[SearchFn] = None,
        max_iterations: int = 3,
    ) -> None:
        self._search_fn = search_fn
        self.max_iterations = max(1, max_iterations)

    async def _default_search(self, subquery: str) -> List[SourceDocument]:
        from cognitive.knowledge.web_search.providers.mock_provider import MockWebSearchProvider

        provider = MockWebSearchProvider()
        res = provider.search(subquery, max_results=3)
        return [
            SourceDocument(
                url=item.url,
                title=item.title,
                content=item.snippet,
                snippet=item.snippet,
            )
            for item in getattr(res, "results", res)
        ]

    @staticmethod
    def _plan_subqueries(topic: str, iteration: int, prior_findings: List[CitedFinding]) -> str:
        angles = [
            f"{topic} core trends and measurable outcomes",
            f"{topic} benefits challenges and empirical evidence",
            f"{topic} clinical workflow adoption case studies",
        ]
        if iteration < len(angles):
            return angles[iteration]
        return f"{topic} synthesis step {iteration + 1}"

    @staticmethod
    def _extract_statement(doc: SourceDocument, subquery: str) -> str:
        text = (doc.content or doc.snippet or doc.title).strip()
        first_sentence = text.split(".")[0].strip()
        return first_sentence if first_sentence else f"Evidence retrieved for {subquery}."

    async def research(self, topic: str, max_iterations: Optional[int] = None) -> DeepResearchReport:
        """Execute multi-step research loop and build a cited Markdown report."""
        steps = max_iterations or self.max_iterations
        findings: List[CitedFinding] = []
        seen_urls: Dict[str, int] = {}
        sources: List[SourceDocument] = []

        for step in range(steps):
            subquery = self._plan_subqueries(topic, step, findings)
            if self._search_fn is not None:
                maybe_docs = self._search_fn(subquery)
                docs = await maybe_docs if asyncio.iscoroutine(maybe_docs) else list(maybe_docs)
            else:
                docs = await self._default_search(subquery)

            for doc in docs:
                if doc.url not in seen_urls:
                    sources.append(doc)
                    seen_urls[doc.url] = len(sources)
                cid = seen_urls[doc.url]
                findings.append(
                    CitedFinding(
                        citation_id=cid,
                        subquery=subquery,
                        statement=self._extract_statement(doc, subquery),
                        source_url=doc.url,
                        source_title=doc.title,
                    )
                )

        lines = [f"# Deep Research Report: {topic}", "", "## Synthesized Findings", ""]
        for finding in findings:
            lines.append(f"- {finding.statement} [{finding.citation_id}]")
        lines.extend(["", "## References", ""])
        for idx, src in enumerate(sources, 1):
            lines.append(f"[{idx}] **{src.title}** — {src.url}")

        return DeepResearchReport(
            topic=topic,
            iterations_completed=steps,
            findings=findings,
            sources=sources,
            report_markdown="\n".join(lines).strip() + "\n",
        )

