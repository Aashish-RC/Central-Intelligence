"""Citation Formatter (Feature 6.33)

Formats citations and reference bibliographies across academic and professional styles:
APA, MLA, Chicago, inline, and footnote formats.
Wires with L3 Knowledge attribution / copyright provenance.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from cognitive.knowledge.provenance.models import ProvenanceTagResult
except ImportError:
    ProvenanceTagResult = Any  # type: ignore


class CitationStyle(str, Enum):
    APA = "apa"
    MLA = "mla"
    CHICAGO = "chicago"
    INLINE = "inline"
    FOOTNOTE = "footnote"


@dataclass
class CitationSource:
    """Canonical representation of an attributable source or knowledge artifact."""
    title: str
    authors: List[str] = field(default_factory=list)  # ["Last, First", "Last2, First2"]
    year: Optional[int | str] = None
    publication: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    access_date: Optional[str] = None
    provenance_tag: Optional[ProvenanceTagResult] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CitationFormatter:
    """Formats source citations into standardized bibliographic representations."""

    def format(self, source: CitationSource, style: CitationStyle | str) -> str:
        """Format a single source per specified citation style."""
        resolved_style = CitationStyle(style) if isinstance(style, str) else style

        if resolved_style == CitationStyle.APA:
            return self._format_apa(source)
        elif resolved_style == CitationStyle.MLA:
            return self._format_mla(source)
        elif resolved_style == CitationStyle.CHICAGO:
            return self._format_chicago(source)
        elif resolved_style == CitationStyle.INLINE:
            return self._format_inline(source)
        elif resolved_style == CitationStyle.FOOTNOTE:
            return self._format_footnote(source)
        return self._format_apa(source)

    def format_from_provenance(
        self,
        provenance: ProvenanceTagResult,
        title: str,
        style: CitationStyle | str = CitationStyle.APA,
        url: Optional[str] = None,
    ) -> str:
        """Construct citation directly from L3 Knowledge license and copyright provenance."""
        authors: List[str] = []
        year: Optional[int] = None

        if hasattr(provenance, "copyright_notices") and provenance.copyright_notices:
            for notice in provenance.copyright_notices:
                if notice.holder and notice.holder not in authors:
                    authors.append(notice.holder)
                if notice.year and not year:
                    year = notice.year

        if not authors:
            authors = ["Central Intelligence Repository"]

        source = CitationSource(
            title=title,
            authors=authors,
            year=year or 2026,
            publication=f"License: {getattr(provenance, 'license_id', 'Proprietary')}",
            url=url,
            provenance_tag=provenance,
        )
        return self.format(source, style)

    def _format_apa(self, source: CitationSource) -> str:
        # APA 7th edition: Author, A. A. (Year). Title. Publication. URL/DOI
        author_str = self._format_authors_apa(source.authors)
        year_str = f"({source.year})." if source.year else "(n.d.)."
        title_str = f"{source.title}."

        parts = [author_str, year_str, title_str]
        if source.publication:
            pub_str = f"*{source.publication}*"
            if source.volume:
                pub_str += f", *{source.volume}*"
                if source.issue:
                    pub_str += f"({source.issue})"
            if source.pages:
                pub_str += f", {source.pages}"
            parts.append(f"{pub_str}.")

        if source.doi:
            parts.append(f"https://doi.org/{source.doi}")
        elif source.url:
            parts.append(source.url)

        return " ".join([p for p in parts if p]).strip()

    def _format_mla(self, source: CitationSource) -> str:
        # MLA 9th edition: Author, First. "Title." Publication, vol, no, year, pp. URL.
        author_str = self._format_authors_mla(source.authors)
        title_str = f'"{source.title}."'
        parts = [author_str, title_str]

        pub_parts: List[str] = []
        if source.publication:
            pub_parts.append(f"*{source.publication}*")
        if source.volume:
            pub_parts.append(f"vol. {source.volume}")
        if source.issue:
            pub_parts.append(f"no. {source.issue}")
        if source.year:
            pub_parts.append(str(source.year))
        if source.pages:
            pub_parts.append(f"pp. {source.pages}")

        if pub_parts:
            parts.append(", ".join(pub_parts) + ".")

        if source.doi:
            parts.append(f"https://doi.org/{source.doi}.")
        elif source.url:
            parts.append(f"{source.url}.")

        return " ".join([p for p in parts if p]).strip()

    def _format_chicago(self, source: CitationSource) -> str:
        # Chicago 17th: Author, First. "Title." Publication vol, no. (Year): pages.
        author_str = self._format_authors_mla(source.authors)
        title_str = f'"{source.title}."'
        pub_str = f"*{source.publication}*" if source.publication else ""
        year_str = f"({source.year})" if source.year else ""
        pages_str = f": {source.pages}" if source.pages else ""
        return f"{author_str} {title_str} {pub_str} {year_str}{pages_str}.".strip()

    def _format_inline(self, source: CitationSource) -> str:
        # Inline: (Lastname, Year) or (Lastname et al., Year)
        if not source.authors:
            author_last = "Anonymous"
        elif len(source.authors) == 1:
            author_last = source.authors[0].split(",")[0].strip()
        elif len(source.authors) == 2:
            a1 = source.authors[0].split(",")[0].strip()
            a2 = source.authors[1].split(",")[0].strip()
            author_last = f"{a1} & {a2}"
        else:
            author_last = f"{source.authors[0].split(',')[0].strip()} et al."

        year_str = str(source.year) if source.year else "n.d."
        return f"({author_last}, {year_str})"

    def _format_footnote(self, source: CitationSource) -> str:
        return f"{self._format_inline(source)}: {source.title}. {source.url or ''}".strip()

    def _format_authors_apa(self, authors: List[str]) -> str:
        if not authors:
            return "Anonymous."
        if len(authors) == 1:
            return f"{authors[0]}."
        if len(authors) == 2:
            return f"{authors[0]}, & {authors[1]}."
        return f"{', '.join(authors[:-1])}, & {authors[-1]}."

    def _format_authors_mla(self, authors: List[str]) -> str:
        if not authors:
            return "Anonymous."
        if len(authors) == 1:
            return f"{authors[0]}."
        if len(authors) == 2:
            return f"{authors[0]}, and {authors[1]}."
        return f"{authors[0]}, et al."

    def format_bibliography(self, sources: List[CitationSource], style: CitationStyle | str) -> List[str]:
        """Format an entire bibliography sorted alphabetically by primary author."""
        sorted_sources = sorted(
            sources,
            key=lambda s: s.authors[0] if s.authors else s.title
        )
        return [self.format(s, style) for s in sorted_sources]

