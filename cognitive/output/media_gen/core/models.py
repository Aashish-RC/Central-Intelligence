"""
Data models for the Pheonix Media Generation pipeline.
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MediaType(str, Enum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SafetyCheckStatus(str, Enum):
    PASSED = "passed"
    FLAGGED = "flagged"
    BLOCKED = "blocked"


class SafetyResult(BaseModel):
    status: SafetyCheckStatus
    reason: Optional[str] = None
    flags: List[str] = Field(default_factory=list)


class MediaRequest(BaseModel):
    id: str = Field(default_factory=lambda: f"mreq_{uuid.uuid4().hex[:10]}")
    media_type: MediaType
    prompt: str
    negative_prompt: Optional[str] = None
    model: str = "default"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 5  # 1 (highest) to 10 (lowest)
    user_id: str = "local-user"
    project_id: str = "default"
    created_at: float = Field(default_factory=time.time)


class MediaArtifact(BaseModel):
    id: str = Field(default_factory=lambda: f"mart_{uuid.uuid4().hex[:10]}")
    request_id: str
    media_type: MediaType
    uri: str
    mime_type: str
    size_bytes: int
    sha256: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class MediaJob(BaseModel):
    id: str = Field(default_factory=lambda: f"mjob_{uuid.uuid4().hex[:10]}")
    request: MediaRequest
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    result: Optional[MediaArtifact] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
