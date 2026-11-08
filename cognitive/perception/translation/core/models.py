"""
Data models for the Pheonix Translation Subsystem.
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class LanguageCode(str, Enum):
    AUTO = "auto"
    EN = "en"
    ES = "es"
    FR = "fr"
    DE = "de"
    ZH = "zh"
    JA = "ja"
    KO = "ko"
    HI = "hi"
    AR = "ar"
    RU = "ru"


class ScriptType(str, Enum):
    LATIN = "latin"
    HANZI = "hanzi"
    HANGUL = "hangul"
    DEVANAGARI = "devanagari"
    ARABIC = "arabic"
    CYRILLIC = "cyrillic"
    UNKNOWN = "unknown"


class LocaleDetectionResult(BaseModel):
    language: str
    script: ScriptType
    confidence: float = 1.0


class TranslationRequest(BaseModel):
    id: str = Field(default_factory=lambda: f"treq_{uuid.uuid4().hex[:10]}")
    text: str
    target_lang: str
    source_lang: str = "auto"
    format: str = "text"
    preserve_formatting: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class TranslationResult(BaseModel):
    request_id: str
    original_text: str
    translated_text: str
    detected_source_lang: str
    target_lang: str
    engine: str
    cached: bool = False
    latency_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)
