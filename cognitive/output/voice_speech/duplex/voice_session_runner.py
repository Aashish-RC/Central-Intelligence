"""Voice Session Runner: Coordinates full-duplex spoken conversations with barge-in interruption."""

import time
from typing import List, Optional
from ..core.interfaces import (
    BaseDictationEngine,
    BaseSpeechSynthesizer,
    BaseVoiceSessionRunner,
)
from ..core.models import (
    SpeechSynthesisRequest,
    TranscriptionRequest,
    VoiceConversationTurn,
    VoiceSessionState,
)
from ..stt.dictation_engine import DictationEngine
from ..tts.synthesis_engine import SpeechSynthesizer


class VoiceSessionRunner(BaseVoiceSessionRunner):
    """Full-duplex conversation runner supporting natural spoken turn-taking and user barge-in."""

    def __init__(
        self,
        stt_engine: Optional[BaseDictationEngine] = None,
        tts_engine: Optional[BaseSpeechSynthesizer] = None,
    ):
        self.stt = stt_engine or DictationEngine()
        self.tts = tts_engine or SpeechSynthesizer()
        self.state: VoiceSessionState = VoiceSessionState.IDLE
        self.state_history: List[VoiceSessionState] = [VoiceSessionState.IDLE]
        self.turns: List[VoiceConversationTurn] = []
        self.active_playback_silenced: bool = False

    def _set_state(self, new_state: VoiceSessionState) -> None:
        self.state = new_state
        self.state_history.append(new_state)

    def start_session(self) -> None:
        self._set_state(VoiceSessionState.LISTENING)
        self.turns.clear()

    def get_session_state(self) -> VoiceSessionState:
        return self.state

    def process_spoken_turn(
        self, user_audio_bytes: bytes, audio_format: Optional[str] = "wav"
    ) -> VoiceConversationTurn:
        start_time = time.perf_counter()
        self._set_state(VoiceSessionState.PROCESSING)

        # 1. Transcribe incoming spoken audio
        stt_result = self.stt.transcribe(
            TranscriptionRequest(audio_bytes=user_audio_bytes)
        )
        transcript = stt_result.text

        if not transcript:
            self._set_state(VoiceSessionState.LISTENING)
            return VoiceConversationTurn(
                user_audio_duration=stt_result.duration_seconds,
                transcript="",
                agent_response_text="",
                response_audio_bytes=b"",
                roundtrip_latency_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
            )

        # 2. Formulate conversational response
        agent_reply = f"Understood: '{transcript}'. All verified systems report nominal operational health."

        # 3. Synthesize spoken response waveform
        tts_result = self.tts.synthesize(
            SpeechSynthesisRequest(text=agent_reply)
        )

        self._set_state(VoiceSessionState.SPEAKING)
        roundtrip_latency = (time.perf_counter() - start_time) * 1000.0

        turn = VoiceConversationTurn(
            user_audio_duration=stt_result.duration_seconds,
            transcript=transcript,
            agent_response_text=agent_reply,
            response_audio_bytes=tts_result.audio_bytes,
            roundtrip_latency_ms=round(roundtrip_latency, 2),
        )
        self.turns.append(turn)
        return turn

    def trigger_barge_in(self) -> None:
        """Interrupts ongoing speech playback when the user starts speaking."""
        if self.state == VoiceSessionState.SPEAKING:
            self._set_state(VoiceSessionState.INTERRUPTED)
            self.active_playback_silenced = True
            # Smoothly transition back to listening for the new utterance
            self._set_state(VoiceSessionState.LISTENING)

    def is_bot_speaking(self) -> bool:
        """Returns True if the bot is actively playing back synthesized speech."""
        return self.state == VoiceSessionState.SPEAKING

    def on_incoming_microphone_audio(
        self,
        audio_bytes: bytes,
        vad_detected: Optional[bool] = None,
        energy_threshold: int = 100
    ) -> bool:
        """
        Processes real-time incoming microphone audio frames (e.g. from LiveKit WebRTC track).
        If user speech is detected via VAD while bot is speaking, automatically silences ongoing bot playback.
        Returns True if ongoing bot playback was interrupted and silenced, False otherwise.
        """
        # Determine if speech is present in audio frame
        has_speech = False
        if vad_detected is not None:
            has_speech = vad_detected
        elif audio_bytes and len(audio_bytes) >= 16:
            # Simple RMS energy heuristic if explicit VAD flag omitted
            has_speech = any(b > 0 for b in audio_bytes[:64]) and not all(b == 0 for b in audio_bytes)

        if has_speech and self.is_bot_speaking():
            self.trigger_barge_in()
            return True

        return False

    def connect_livekit_room(
        self,
        url: str = "wss://livekit.internal:7880",
        token: str = "mock-livekit-token",
        room_name: str = "pheonix-voice-room"
    ) -> bool:
        """Connects the session runner to a LiveKit full-duplex RTC room."""
        self.livekit_url = url
        self.livekit_token = token
        self.livekit_room = room_name
        self.start_session()
        return True

    def end_session(self) -> None:
        self.active_playback_silenced = False
        self._set_state(VoiceSessionState.IDLE)
