"""Core data models for Web Search, Scraping, and Citation Verification."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WebSearchResultItem(BaseModel):
    """Normalized search engine hit."""
    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="Web page title")
    url: str = Field(..., description="Target HTTPS URL")
    snippet: str = Field(default="", description="Search snippet / excerpt")
    domain: str = Field(default="", description="Host domain, e.g. 'docs.python.org'")
    published_date: Optional[str] = Field(default=None)


class ScrapedPage(BaseModel):
    """Scraped and parsed web document."""
    model_config = ConfigDict(extra="ignore")

    url: str
    title: str
    markdown_content: str = Field(default="", description="Cleaned, boilerplate-stripped markdown")
    clean_text: str = Field(default="", description="Normalized raw plain text")
    content_sha256: str = Field(..., description="Content hash for tamper-evident provenance")
    links: List[str] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=utc_now)


class WebCitation(BaseModel):
    """Verifiable source grounding referencing a specific web excerpt."""
    model_config = ConfigDict(extra="ignore")

    url: str = Field(..., description="Authoritative source URL")
    domain: str = Field(..., description="Hostname of source")
    title: str = Field(..., description="Page title")
    quote_text: str = Field(..., description="Exact quoted supporting text from the page")
    content_sha256: str = Field(..., description="SHA-256 of the scraped content")
    retrieved_at: datetime = Field(default_factory=utc_now)


class SourceSupportCheck(BaseModel):
    """Verification result evaluating whether a claim is supported by a source document."""
    model_config = ConfigDict(extra="ignore")

    claim: str = Field(..., description="Target statement or hypothesis tested")
    is_supported: bool = Field(..., description="True if support_score exceeds threshold")
    support_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score [0..1]")
    supporting_quote: Optional[str] = Field(default=None, description="Best matching evidence sentence")
    citation: Optional[WebCitation] = Field(default=None, description="Structured citation anchor")


class SearchResult(BaseModel):
    """Aggregated web search and scraped content result with verifiable citations."""
    model_config = ConfigDict(extra="ignore")

    query: str
    results: List[WebSearchResultItem] = Field(default_factory=list)
    citations: List[WebCitation] = Field(default_factory=list)
    markdown_content: str = Field(default="", description="Consolidated markdown extract from search hits")

    def __iter__(self):
        return iter(self.results)

    def __getitem__(self, idx):
        return self.results[idx]

    def __len__(self):
        return len(self.results)
