"""Abstract interfaces for Pheonix Voice and Speech components."""

from abc import ABC, abstractmethod
from typing import Optional
from .models import (
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    TranscriptionRequest,
    TranscriptionResult,
    VoiceConversationTurn,
    VoiceSessionState,
)


class BaseDictationEngine(ABC):
    """Interface for transcribing audio speech into text."""

    @abstractmethod
    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        pass


class BaseSpeechSynthesizer(ABC):
    """Interface for synthesizing text into speech audio waveforms."""

    @abstractmethod
    def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResult:
        pass


class BaseVoiceSessionRunner(ABC):
    """Interface for managing real-time duplex voice conversations with barge-in support."""

    @abstractmethod
    def start_session(self) -> None:
        pass

    @abstractmethod
    def get_session_state(self) -> VoiceSessionState:
        pass

    @abstractmethod
    def process_spoken_turn(
        self, user_audio_bytes: bytes, audio_format: Optional[str] = "wav"
    ) -> VoiceConversationTurn:
        pass

    @abstractmethod
    def trigger_barge_in(self) -> None:
        pass

    @abstractmethod
    def end_session(self) -> None:
        pass
