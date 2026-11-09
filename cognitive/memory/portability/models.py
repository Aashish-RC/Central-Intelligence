"""Data models for Cross-Assistant Memory Import/Export (Features 2.46, 2.50)."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MemoryPortabilityFormat(str, Enum):
    """Supported export/import formats."""
    CI_STANDARD = "ci_standard"
    CHATGPT = "chatgpt"
    CLAUDE = "claude"


class StandardTurnRecord(BaseModel):
    id: Optional[str] = None
    role: str
    content: str
    timestamp: Optional[str] = None
    session_id: Optional[str] = "default"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StandardFactRecord(BaseModel):
    subject: str
    predicate: str
    object: str
    confidence_score: float = 1.0
    context: Optional[str] = None
    session_id: Optional[str] = None


class StandardMemoryExport(BaseModel):
    version: str = "1.0.0"
    exported_at: str
    user_id: str
    format: MemoryPortabilityFormat
    turns: List[StandardTurnRecord] = Field(default_factory=list)
    facts: List[StandardFactRecord] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ImportStats(BaseModel):
    format: MemoryPortabilityFormat
    turns_imported: int = 0
    facts_imported: int = 0
    sessions_discovered: int = 0
    success: bool = True
    errors: List[str] = Field(default_factory=list)
