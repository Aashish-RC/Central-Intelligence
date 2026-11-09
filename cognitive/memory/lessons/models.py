"""Data models for Lessons-Learned Auto-Extractor.

Features: 2.49 (Lessons-Learned Auto-Extraction), 7.27 (Cognitive Reflection)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LessonCategory(str, Enum):
    """Classification of lessons learned from agent execution."""
    TOOL_FAILURE = "tool_failure"
    USER_CORRECTION = "user_correction"
    SYNTAX_BUG = "syntax_bug"
    API_MISMATCH = "api_mismatch"
    ENVIRONMENT_CONFIG = "environment_config"
    SAFETY_RULE = "safety_rule"
    GENERAL = "general"


class LessonRecord(BaseModel):
    """An actionable lesson distilled from past agent mistakes or user feedback."""
    model_config = ConfigDict(extra="ignore")

    lesson_id: str = Field(default_factory=lambda: f"lsn_{uuid.uuid4().hex[:8]}")
    title: str = Field(..., description="Short descriptive title of the lesson")
    category: LessonCategory = Field(default=LessonCategory.GENERAL)
    trigger_context: str = Field(..., description="Keywords, tool names, or task context where this lesson applies")
    mistake: str = Field(..., description="What went wrong or caused the issue")
    resolution: str = Field(..., description="How the issue was corrected")
    rule: str = Field(..., description="Imperative operational guideline for future iterations")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    application_count: int = Field(default=0, ge=0)
    source_session_id: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
