"""Core data models for Global Hybrid Search."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CorpusType(str, Enum):
    CHAT = "chat"
    CONVERSATION = "conversation"
    FILE = "file"
    NOTE = "note"
    MEMORY = "memory"
    ARTIFACT = "artifact"


class SearchDocument(BaseModel):
    """Unified indexed document spanning chats, files, notes, or memory."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique composite identifier, e.g. 'note:uuid'")
    corpus_type: CorpusType = Field(..., description="Domain corpus entity type")
    tenant_id: str = Field(default="default", description="Strict tenant boundary")
    project_id: str = Field(default="default", description="Strict workspace/project boundary")
    title: str = Field(..., description="Document or asset title")
    content: str = Field(default="", description="Searchable textual body")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata attributes")
    embedding: Optional[List[float]] = Field(default=None, description="Dense embedding vector")
    timestamp: datetime = Field(default_factory=utc_now)


class SearchQuery(BaseModel):
    """Hybrid query request specifying text, filters, and blending weights."""
    model_config = ConfigDict(extra="ignore")

    query_text: str = Field(..., min_length=1, description="Natural language or keyword query")
    tenant_id: str = Field(default="default", description="Tenant isolation boundary")
    project_id: str = Field(default="default", description="Workspace isolation boundary")
    corpus_types: Optional[List[CorpusType]] = Field(default=None, description="Filter by corpora")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags (OR matching)")
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return")
    hybrid_alpha: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight balance: 0.0 pure lexical, 1.0 pure vector, 0.5 balanced RRF",
    )


class SearchResult(BaseModel):
    """Ranked search hit combining lexical and vector evidence."""
    model_config = ConfigDict(extra="ignore")

    document: SearchDocument
    rrf_score: float = Field(..., description="Composite Reciprocal Rank Fusion score")
    lexical_rank: Optional[int] = Field(default=None, description="Rank in BM25 lexical results (1-based)")
    vector_rank: Optional[int] = Field(default=None, description="Rank in vector similarity results (1-based)")
    highlights: List[str] = Field(default_factory=list, description="Snippet excerpts with matching keywords")


class SearchResponse(BaseModel):
    """Unified search response payload."""
    model_config = ConfigDict(extra="ignore")

    query: str
    tenant_id: str = Field(default="default", description="Tenant isolation boundary")
    project_id: str
    total_hits: int
    results: List[SearchResult]
