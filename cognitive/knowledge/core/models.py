"""Core data models for Knowledge and Docs: Notes, Notebooks, and Citations."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CellType(str, Enum):
    MARKDOWN = "markdown"
    SOURCE_QUERY = "source_query"
    GROUNDED_EXCERPT = "grounded_excerpt"
    SYNTHESIS = "synthesis"


class CitationAnchor(BaseModel):
    """Verifiable source grounding referencing a stored file or memory artifact."""
    model_config = ConfigDict(extra="ignore")

    quote_text: str = Field(..., description="Direct quote or excerpt from the grounding source")
    file_id: Optional[str] = Field(default=None, description="Storage blob or file UUID/path")
    sha256: Optional[str] = Field(default=None, description="Content-addressed hash of original asset")
    source_name: Optional[str] = Field(default=None, description="Human-friendly file name or turn label")
    chunk_index: Optional[int] = Field(default=None, description="Zero-indexed chunk location")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class BacklinkRef(BaseModel):
    """Reference tracking an incoming wiki-link to a note."""
    model_config = ConfigDict(extra="ignore")

    source_note_id: str
    source_title: str
    target_title: str
    context_snippet: str = ""


class Note(BaseModel):
    """Atomic markdown note with frontmatter metadata, tags, and link tracking."""
    model_config = ConfigDict(extra="ignore")

    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(default="default", description="Tenant scope identifier")
    project_id: str = Field(default="default", description="Workspace or project isolation boundary")
    title: str = Field(..., description="Unique title within the project")
    slug: str = Field(default="", description="URL/link friendly identifier")
    content: str = Field(default="", description="Raw Markdown note content")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary frontmatter key-values")
    outgoing_links: List[str] = Field(default_factory=list, description="Wiki-links [[Target]] found in note")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class NotebookCell(BaseModel):
    """An individual interactive or synthesized cell in a source-grounded notebook."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    cell_type: CellType = Field(default=CellType.MARKDOWN)
    content: str = Field(default="", description="Markdown text, query string, or prompt")
    output: Optional[str] = Field(default=None, description="Evaluation output or grounded summary")
    citations: List[CitationAnchor] = Field(default_factory=list, description="Verified source anchors")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Notebook(BaseModel):
    """Interactive, source-grounded research notebook."""
    model_config = ConfigDict(extra="ignore")

    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(default="default", description="Tenant scope identifier")
    project_id: str = Field(default="default", description="Project isolation boundary")
    title: str = Field(..., description="Notebook title")
    description: Optional[str] = Field(default=None)
    cells: List[NotebookCell] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
