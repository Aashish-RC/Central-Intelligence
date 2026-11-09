"""Data models for Point-in-Time Knowledge Snapshots (Feature 3.24)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class KnowledgeItemSnapshot(BaseModel):
    id: str
    title: str
    content: str
    item_type: str = "note"       # "note", "doc", "chunk", "graph_node"
    version: int = 1
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class GraphRelationshipSnapshot(BaseModel):
    source: str
    relation: str
    target: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeSnapshot(BaseModel):
    snapshot_id: str
    tag: Optional[str] = None
    description: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    items: List[KnowledgeItemSnapshot] = Field(default_factory=list)
    relationships: List[GraphRelationshipSnapshot] = Field(default_factory=list)
    total_items: int = 0
    total_relationships: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SnapshotDiffResult(BaseModel):
    base_snapshot_id: str
    target_snapshot_id: str
    added_items: List[KnowledgeItemSnapshot] = Field(default_factory=list)
    removed_items: List[KnowledgeItemSnapshot] = Field(default_factory=list)
    modified_items: List[Dict[str, Any]] = Field(default_factory=list)
    added_relationships: List[GraphRelationshipSnapshot] = Field(default_factory=list)
    removed_relationships: List[GraphRelationshipSnapshot] = Field(default_factory=list)
