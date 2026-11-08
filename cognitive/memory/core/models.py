"""Data contracts and Pydantic schemas for the Fused Dynamic Memory Layer."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class FactCategory(str, Enum):
    """Categorization for extracted atomic facts."""
    PREFERENCE = "preference"
    RULE = "rule"
    RELATIONSHIP = "relationship"
    ENTITY = "entity"
    CONSTRAINT = "constraint"
    FACT = "fact"


class TurnRole(str, Enum):
    """Roles in conversation turns."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MemoryRecord(BaseModel):
    """Primary archival / semantic memory record (Tier 3)."""
    model_config = ConfigDict(extra="ignore")

    id: UUID = Field(default_factory=uuid4, description="Unique memory record UUID")
    tenant_id: str = Field(default="default", description="Tenant scope identifier")
    user_id: str = Field(..., description="Unique identifier for the user/agent owner")
    project_id: str = Field(default="default", description="Project scope identifier")
    session_id: Optional[str] = Field(default=None, description="Source session ID if applicable")
    text: str = Field(..., description="The textual content of the memory")
    embedding: Optional[List[float]] = Field(default=None, description="Dense vector embedding")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary searchable metadata")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in this memory")
    is_active: bool = Field(default=True, description="Whether this memory is currently valid")
    created_at: datetime = Field(default_factory=utc_now, description="UTC creation timestamp")
    updated_at: datetime = Field(default_factory=utc_now, description="UTC last update timestamp")
    last_accessed_at: datetime = Field(default_factory=utc_now, description="UTC timestamp of last recall")
    access_count: int = Field(default=0, ge=0, description="Number of times this memory was retrieved")


class FactItem(BaseModel):
    """Structured atomic key-value fact item (Tier 2)."""
    model_config = ConfigDict(extra="ignore")

    id: UUID = Field(default_factory=uuid4, description="Unique fact UUID")
    tenant_id: str = Field(default="default", description="Tenant scope identifier")
    user_id: str = Field(..., description="Owner user ID")
    project_id: str = Field(default="default", description="Project scope identifier")
    key: str = Field(..., description="Normalized lookup key (e.g. 'preferred_language', 'location')")
    value: str = Field(..., description="Fact value (e.g. 'Go', 'Tokyo')")
    category: FactCategory = Field(default=FactCategory.FACT, description="Fact taxonomy category")
    source_event_id: Optional[UUID] = Field(default=None, description="UUID of the triggering turn/event")
    version: int = Field(default=1, ge=1, description="Version number for key mutation tracking")
    is_active: bool = Field(default=True, description="Active status; set to False when superseded")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    superseded_by: Optional[UUID] = Field(default=None, description="UUID of the newer fact replacing this")
    created_at: datetime = Field(default_factory=utc_now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=utc_now, description="Update timestamp")
    last_accessed_at: datetime = Field(default_factory=utc_now, description="Last access timestamp")
    access_count: int = Field(default=0, ge=0, description="Recall counter for soft decay")


class Turn(BaseModel):
    """A single conversational or execution event in working memory (Tier 1)."""
    model_config = ConfigDict(extra="ignore")

    id: UUID = Field(default_factory=uuid4, description="Turn UUID")
    tenant_id: str = Field(default="default", description="Tenant scope identifier")
    session_id: str = Field(..., description="Session identifier")
    user_id: str = Field(..., description="User identifier")
    project_id: str = Field(default="default", description="Project scope identifier")
    role: TurnRole = Field(..., description="Speaker role")
    content: str = Field(..., description="Turn message text")
    tokens: int = Field(default=0, ge=0, description="Estimated token count")
    timestamp: datetime = Field(default_factory=utc_now, description="Turn timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata")


class SessionState(BaseModel):
    """Working session state container."""
    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(..., description="Session identifier")
    tenant_id: str = Field(default="default", description="Tenant scope identifier")
    user_id: str = Field(..., description="User identifier")
    turns: List[Turn] = Field(default_factory=list, description="Working conversation window")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextPackage(BaseModel):
    """Concentrated prompt injection context (< 500 tokens)."""
    model_config = ConfigDict(extra="ignore")

    tenant_id: str = Field(default="default", description="Tenant scope identifier")
    user_id: str = Field(..., description="Target user ID")
    session_id: Optional[str] = Field(default=None, description="Active session ID")
    working_memory: List[Turn] = Field(default_factory=list, description="Tier 1 recent turns")
    core_facts: List[FactItem] = Field(default_factory=list, description="Tier 2 active key-value facts")
    archival_matches: List[MemoryRecord] = Field(default_factory=list, description="Tier 3 semantic hits")
    formatted_prompt: str = Field(..., description="Concentrated, token-budgeted system prompt context")
    token_count: int = Field(default=0, ge=0, description="Exact/estimated token count")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.token_count

    @property
    def context_str(self) -> str:
        return self.formatted_prompt

    @property
    def facts(self) -> List[FactItem]:
        return self.core_facts


class ExtractedMemoryPlan(BaseModel):
    """Plan generated by the Extractor Stitch."""
    model_config = ConfigDict(extra="ignore")

    facts_to_add: List[FactItem] = Field(default_factory=list, description="New or updated facts")
    keys_to_invalidate: List[str] = Field(default_factory=list, description="Fact keys superseded")
    archival_text: Optional[str] = Field(default=None, description="Summary to store in Tier 3 vector store")
    entities: List[str] = Field(default_factory=list, description="Named entities identified")
    summary: Optional[str] = Field(default=None, description="Brief turn summary")


class SourceProvenance(BaseModel):
    """Origin tracking for memory items."""
    model_config = ConfigDict(extra="ignore")

    source_type: str = "conversation"  # 'conversation' | 'file' | 'manual' | 'agent'
    source_ref: Optional[str] = None   # session_id, file URI e.g. pheonix://files/..., turn_id
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extracted_at: datetime = Field(default_factory=utc_now)


class MemorySourceItem(BaseModel):
    """Item in the memory sources view."""
    model_config = ConfigDict(extra="ignore")

    item_id: str
    item_type: str  # 'fact' | 'archival'
    project_id: str = "default"
    user_id: str
    summary_text: str
    provenance: SourceProvenance
    created_at: datetime = Field(default_factory=utc_now)
    is_active: bool = True


class MemorySourcesView(BaseModel):
    """Aggregate view of all memory sources and facts for inspection and deletion."""
    model_config = ConfigDict(extra="ignore")

    project_id: str = "default"
    user_id: str
    total_sources: int = 0
    facts_count: int = 0
    archival_count: int = 0
    items: List[MemorySourceItem] = Field(default_factory=list)
