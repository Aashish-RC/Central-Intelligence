"""Speech-to-Speech Real-Time Voice Event Loop."""

import asyncio
from typing import Any, AsyncGenerator, Callable, Dict, Optional
from agent.core.manifest import AgentManifest
from .livekit_adapter import LiveKitAdapter


class VoiceAgentLoop:
    """Manages full duplex real-time speech event loop."""

    def __init__(
        self,
        manifest: AgentManifest,
        livekit_adapter: Optional[LiveKitAdapter] = None,
        runner: Optional[Any] = None,
    ):
        self.manifest = manifest
        self.livekit = livekit_adapter or LiveKitAdapter()
        self.runner = runner
        self._is_active = False

    async def start_session(self, room_id: str, participant_id: str) -> Dict[str, Any]:
        """Initialize and connect voice session."""
        self._is_active = True
        conn_info = self.livekit.get_connection_info(room_name=room_id, participant_identity=participant_id)
        return {
            "status": "connected",
            "room_id": room_id,
            "participant_id": participant_id,
            "webrtc": conn_info,
        }

    async def handle_audio_frame(self, audio_chunk: bytes) -> AsyncGenerator[str, None]:
        """Processes incoming audio chunk, passes through STT, runner, and returns speech tokens."""
        if not self._is_active:
            return

        # Simulated transcription from audio buffer
        transcribed_text = f"[Speech input: {len(audio_chunk)} audio bytes]"

        # Stream response back
        yield f"Acknowledged speech: {transcribed_text}"

    async def stop_session(self) -> None:
        """Tear down voice session."""
        self._is_active = False
