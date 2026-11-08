"""Core data models for Pheonix Voice and Speech Engine."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AudioFormat(str, Enum):
    WAV = "wav"
    MP3 = "mp3"
    PCM_16BIT = "pcm_16bit"
    OGG = "ogg"


class VoiceSessionState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


class TranscriptionRequest(BaseModel):
    audio_bytes: bytes
    audio_format: AudioFormat = AudioFormat.WAV
    sample_rate: int = 16000
    language: Optional[str] = "en"


class TranscriptionSegment(BaseModel):
    start_time: float
    end_time: float
    text: str
    confidence: float = 0.95


class TranscriptionResult(BaseModel):
    text: str
    confidence: float = 0.95
    duration_seconds: float = 1.0
    segments: List[TranscriptionSegment] = Field(default_factory=list)


class SpeechSynthesisRequest(BaseModel):
    text: str
    voice_id: str = "aura-orpheus"
    speed: float = 1.0
    audio_format: AudioFormat = AudioFormat.WAV


class SpeechSynthesisResult(BaseModel):
    audio_bytes: bytes
    audio_format: AudioFormat = AudioFormat.WAV
    duration_seconds: float = 1.0
    sample_rate: int = 24000


class VoiceConversationTurn(BaseModel):
    turn_id: str = Field(default_factory=lambda: f"turn_{uuid.uuid4().hex[:6]}")
    user_audio_duration: float
    transcript: str
    agent_response_text: str
    response_audio_bytes: bytes
    roundtrip_latency_ms: float
    timestamp: datetime = Field(default_factory=utc_now)
