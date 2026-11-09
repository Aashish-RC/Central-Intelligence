"""Data models for Versioned Memory Snapshots and Rollback of Learned Adaptations (Feature 2.51)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FactSnapshotItem(BaseModel):
    id: Optional[str] = None
    key: str
    value: str
    category: str = "fact"
    confidence_score: float = 1.0
    context: Optional[str] = None


class LessonSnapshotItem(BaseModel):
    lesson_id: str
    title: str
    category: str
    trigger_context: str
    mistake: str
    resolution: str
    rule: str
    confidence: float = 0.85


class MemorySnapshot(BaseModel):
    id: str
    user_id: str
    tag: Optional[str] = None
    description: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    facts: List[FactSnapshotItem] = Field(default_factory=list)
    lessons: List[LessonSnapshotItem] = Field(default_factory=list)
    turn_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RollbackResult(BaseModel):
    success: bool
    snapshot_id: str
    user_id: str
    restored_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    facts_restored: int = 0
    facts_removed: int = 0
    lessons_restored: int = 0
    lessons_removed: int = 0
    message: str = "Rollback executed successfully"
