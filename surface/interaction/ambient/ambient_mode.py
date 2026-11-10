"""Ambient Mode & Wake Word Detection (L18 Interaction - Tasks 18.34-18.37).

Provides opt-in ambient background listening, on-device lightweight wake word
detection, and real-time visual presence status indicators.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AmbientState(str, Enum):
    IDLE_DISABLED = "idle_disabled"
    ARMED_LISTENING_WAKE_WORD = "armed_listening_wake_word"
    ACTIVE_LISTENING = "active_listening"
    PROCESSING = "processing"
    RESPONDING = "responding"


@dataclass
class PresenceIndicator:
    """Status of the on-screen / peripheral visual presence indicator."""
    is_active: bool = False
    color: str = "off"  # "off", "amber_armed", "green_active", "pulse_blue"
    badge_text: str = "Dormant"
    is_recording_audio: bool = False
    last_updated: float = field(default_factory=time.time)


class AmbientModeManager:
    """Manages always-listening ambient lifecycle with wake word activation."""

    def __init__(self, wake_words: Optional[List[str]] = None) -> None:
        self.wake_words = [w.lower() for w in (wake_words or ["hey central", "central", "computer"])]
        self.state = AmbientState.IDLE_DISABLED
        self.presence = PresenceIndicator()
        self.is_opted_in: bool = False
        self._listeners: List[Callable[[AmbientState, PresenceIndicator], None]] = []

    def add_presence_listener(self, callback: Callable[[AmbientState, PresenceIndicator], None]) -> None:
        """Register UI presence updates."""
        self._listeners.append(callback)

    def _notify(self) -> None:
        for cb in self._listeners:
            try:
                cb(self.state, self.presence)
            except Exception as exc:
                logger.error("Error in presence listener: %s", exc)

    def opt_in_and_arm(self, user_consent: bool = True) -> bool:
        """Opt in to ambient mode and arm on-device wake-word detection."""
        if not user_consent:
            self.disarm()
            return False

        self.is_opted_in = True
        self.state = AmbientState.ARMED_LISTENING_WAKE_WORD
        self.presence = PresenceIndicator(
            is_active=True,
            color="amber_armed",
            badge_text="Listening for wake word",
            is_recording_audio=False,
            last_updated=time.time(),
        )
        self._notify()
        logger.info("Ambient mode armed. Wake words: %s", self.wake_words)
        return True

    def disarm(self) -> None:
        """Disable ambient mode completely."""
        self.is_opted_in = False
        self.state = AmbientState.IDLE_DISABLED
        self.presence = PresenceIndicator(
            is_active=False,
            color="off",
            badge_text="Dormant",
            is_recording_audio=False,
            last_updated=time.time(),
        )
        self._notify()
        logger.info("Ambient mode disarmed.")

    def process_audio_frame(self, transcription_or_phrase: str) -> bool:
        """Analyze incoming audio stream for wake words.

        Returns True if wake word is detected and active listening starts.
        """
        if not self.is_opted_in or self.state == AmbientState.IDLE_DISABLED:
            return False

        cleaned = transcription_or_phrase.lower().strip()

        # Check for any wake word match
        matched = any(w in cleaned for w in self.wake_words)
        if matched:
            self.state = AmbientState.ACTIVE_LISTENING
            self.presence = PresenceIndicator(
                is_active=True,
                color="green_active",
                badge_text="Active Listening",
                is_recording_audio=True,
                last_updated=time.time(),
            )
            self._notify()
            logger.info("Wake word matched in phrase '%s'! AI started active listening.", cleaned)
            return True

        return False

    def finish_utterance(self) -> None:
        """After utterance finishes processing, return to armed state."""
        if self.is_opted_in:
            self.state = AmbientState.ARMED_LISTENING_WAKE_WORD
            self.presence = PresenceIndicator(
                is_active=True,
                color="amber_armed",
                badge_text="Listening for wake word",
                is_recording_audio=False,
                last_updated=time.time(),
            )
            self._notify()
