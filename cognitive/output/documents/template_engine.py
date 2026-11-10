"""Document Assembly Template Engine (Features 6.25 - 6.28)

Assembles comprehensive multi-section reports with automatic Table of Contents (TOC),
citations, slide decks, and embedded multimedia/tables.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DocumentType(str, Enum):
    REPORT = "report"
    SLIDES = "slides"
    EXECUTIVE_BRIEF = "executive_brief"
    TECHNICAL_SPEC = "technical_spec"


@dataclass
class ReportSection:
    """Individual section within an assembled document."""
    id: str
    title: str
    content: str
    level: int = 1
    subsections: List[ReportSection] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    embedded_media: Optional[Dict[str, Any]] = None


@dataclass
class AssembledDocument:
    """Fully synthesized document output with TOC and metadata."""
    title: str
    doc_type: DocumentType
    toc_markdown: str
    body_markdown: str
    full_markdown: str
    sections_count: int
    citations_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentTemplateEngine:
    """Engine compiling structured section inputs into unified publications."""

    def build_report(
        self,
        title: str,
        sections: List[ReportSection],
        author: str = "Central Intelligence System",
        doc_type: DocumentType = DocumentType.REPORT,
        include_citations: bool = True,
        extra_citations: Optional[List[str]] = None,
    ) -> AssembledDocument:
        """Assemble a multi-section document with a synthesized Table of Contents."""
        toc_lines: List[str] = ["## Table of Contents\n"]
        body_parts: List[str] = []
        all_citations: List[str] = list(extra_citations or [])

        # Header metadata block
        header = [
            f"# {title}\n",
            f"**Author:** {author}  ",
            f"**Type:** {doc_type.value.replace('_', ' ').title()}  ",
            "---\n",
        ]
        body_parts.append("\n".join(header))

        for idx, section in enumerate(sections, start=1):
            sec_num = f"{idx}.0"
            anchor = self._slugify(f"{sec_num}-{section.title}")
            toc_lines.append(f"- [{sec_num} {section.title}](#{anchor})")

            body_parts.append(f"## <a id='{anchor}'></a>{sec_num} {section.title}\n")
            body_parts.append(f"{section.content.strip()}\n")

            if section.embedded_media:
                media_type = section.embedded_media.get("type", "image")
                media_url = section.embedded_media.get("url", "")
                caption = section.embedded_media.get("caption", "")
                if media_type == "image":
                    body_parts.append(f"![{caption}]({media_url})\n*{caption}*\n")
                elif media_type == "table":
                    body_parts.append(f"{section.embedded_media.get('table_markdown', '')}\n")

            for sub_idx, sub in enumerate(section.subsections, start=1):
                sub_num = f"{idx}.{sub_idx}"
                sub_anchor = self._slugify(f"{sub_num}-{sub.title}")
                toc_lines.append(f"  - [{sub_num} {sub.title}](#{sub_anchor})")
                body_parts.append(f"### <a id='{sub_anchor}'></a>{sub_num} {sub.title}\n")
                body_parts.append(f"{sub.content.strip()}\n")
                all_citations.extend(sub.citations)

            all_citations.extend(section.citations)

        # Bibliography section if requested
        unique_citations = list(dict.fromkeys(all_citations))
        if include_citations and unique_citations:
            bib_anchor = "references-and-citations"
            toc_lines.append(f"- [References & Citations](#{bib_anchor})")
            body_parts.append(f"## <a id='{bib_anchor}'></a>References & Citations\n")
            for c in unique_citations:
                body_parts.append(f"* {c}")
            body_parts.append("")

        toc_markdown = "\n".join(toc_lines)
        full_markdown = "\n".join([
            body_parts[0],       # Title and header
            toc_markdown + "\n\n---",
            *body_parts[1:],     # Sections and citations
        ])

        return AssembledDocument(
            title=title,
            doc_type=doc_type,
            toc_markdown=toc_markdown,
            body_markdown="\n".join(body_parts[1:]),
            full_markdown=full_markdown,
            sections_count=len(sections),
            citations_count=len(unique_citations),
            metadata={"author": author},
        )

    @staticmethod
    def _slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        return re.sub(r'[\s_-]+', '-', text)

