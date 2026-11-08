"""LiveKit WebRTC Low-Latency Voice Streaming Adapter."""

import os
from typing import Any, Dict, Optional


class LiveKitAdapter:
    """Manages LiveKit WebRTC room creation and audio stream tokens."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ):
        self.api_url = api_url or os.getenv("LIVEKIT_URL", "wss://livekit.example.com")
        self.api_key = api_key or os.getenv("LIVEKIT_API_KEY", "devkey")
        self.api_secret = api_secret or os.getenv("LIVEKIT_API_SECRET", "secret")

    def generate_token(self, room_name: str, participant_identity: str) -> str:
        """Generate access token for WebRTC client connection."""
        try:
            # Dynamic import of livekit-api if present
            from livekit import api
            token = api.AccessToken(self.api_key, self.api_secret) \
                .with_identity(participant_identity) \
                .with_name(participant_identity) \
                .with_grants(api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                ))
            return token.to_jwt()
        except ImportError:
            # Fallback simulated token when livekit package is not installed
            import base64
            simulated_payload = f"simulated-jwt:{self.api_key}:{room_name}:{participant_identity}"
            return base64.b64encode(simulated_payload.encode()).decode()

    def get_connection_info(self, room_name: str, participant_identity: str) -> Dict[str, Any]:
        """Return WebRTC connection bundle for front-end clients."""
        return {
            "server_url": self.api_url,
            "room_name": room_name,
            "participant_identity": participant_identity,
            "token": self.generate_token(room_name, participant_identity),
        }
