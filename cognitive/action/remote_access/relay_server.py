"""Zero-Knowledge WebSocket Relay Server for Remote Access.

Forwards end-to-end encrypted frames between paired devices without inspecting plaintext.
Enforces device authorization via PairedDeviceRegistry and disconnects revoked devices mid-connection.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, List, Optional
from websockets.sync.server import ServerConnection, serve

from remote_access.core.device_registry import PairedDeviceRegistry
from remote_access.core.models import EncryptedFrame

logger = logging.getLogger(__name__)


class WebSocketRelayServer:
    """Zero-knowledge WebSocket relay forwarding authenticated encrypted frames."""

    def __init__(self, registry: Optional[PairedDeviceRegistry] = None):
        self.registry = registry or PairedDeviceRegistry()
        self._active_connections: Dict[str, ServerConnection] = {}
        self._lock = threading.Lock()
        self.server = None
        self.thread: Optional[threading.Thread] = None
        self.host: str = "127.0.0.1"
        self.port: int = 0
        self.forwarded_count: int = 0
        self.rejected_count: int = 0
        # Recorded payloads inspected by relay (for zero-knowledge audit)
        self.recorded_relay_payloads: List[str] = []

    def start(self, host: str = "127.0.0.1", port: int = 0) -> str:
        """Starts the WebSocket relay server on the specified host and port."""
        self.host = host
        self.server = serve(self._handle_client, host, port)
        self.port = self.server.socket.getsockname()[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.get_url()

    def get_url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    def stop(self) -> None:
        """Stops the relay server and closes all active connections."""
        if self.server:
            with self._lock:
                for dev_id, conn in list(self._active_connections.items()):
                    try:
                        conn.close(4000, "Relay server stopping")
                    except Exception:
                        pass
                self._active_connections.clear()
            self.server.shutdown()
            self.server = None

    def revoke_device(self, device_id: str) -> bool:
        """Revokes a device in the registry and terminates its active WebSocket session immediately."""
        revoked = self.registry.revoke(device_id)
        with self._lock:
            conn = self._active_connections.pop(device_id, None)
            if conn:
                try:
                    conn.close(4003, "Device revoked")
                except Exception:
                    pass
        return revoked

    def _handle_client(self, websocket: ServerConnection) -> None:
        registered_device_id: Optional[str] = None
        try:
            for raw_message in websocket:
                # Disconnect if previously registered device has been revoked
                if registered_device_id and not self.registry.is_authorized(registered_device_id):
                    websocket.close(4003, "Session revoked mid-connection")
                    break

                try:
                    data = json.loads(raw_message)
                except Exception:
                    continue

                msg_type = data.get("type", "message")

                # 1. Device Registration / Handshake
                if msg_type == "register":
                    device_id = data.get("device_id")
                    if not device_id or not self.registry.is_authorized(device_id):
                        self.rejected_count += 1
                        websocket.send(json.dumps({"type": "error", "message": "Unauthorized or unpaired device"}))
                        websocket.close(4003, "Unauthorized device")
                        return

                    registered_device_id = device_id
                    with self._lock:
                        self._active_connections[device_id] = websocket
                    websocket.send(json.dumps({"type": "registered", "device_id": device_id}))
                    continue

                # 2. Forwarding Encrypted Frame
                elif msg_type == "frame" or "ciphertext" in data:
                    frame_data = data.get("frame", data)
                    sender_id = frame_data.get("sender_id")
                    recipient_id = frame_data.get("recipient_id")

                    # Verify sender and recipient authorization
                    if not sender_id or not self.registry.is_authorized(sender_id):
                        self.rejected_count += 1
                        websocket.send(json.dumps({"type": "error", "message": "Sender is unauthorized or revoked"}))
                        websocket.close(4003, "Sender unauthorized")
                        return

                    if not recipient_id or not self.registry.is_authorized(recipient_id):
                        self.rejected_count += 1
                        websocket.send(json.dumps({"type": "error", "message": "Recipient is unauthorized or revoked"}))
                        continue

                    # Record raw message seen by relay for zero-knowledge audit
                    self.recorded_relay_payloads.append(str(raw_message))

                    # Forward to recipient
                    with self._lock:
                        recipient_ws = self._active_connections.get(recipient_id)
                        # Check recipient active status
                        if recipient_ws and self.registry.is_authorized(recipient_id):
                            try:
                                recipient_ws.send(json.dumps({
                                    "type": "frame",
                                    "frame": frame_data,
                                }))
                                self.forwarded_count += 1
                            except Exception:
                                self._active_connections.pop(recipient_id, None)
                        elif recipient_ws and not self.registry.is_authorized(recipient_id):
                            # Recipient was revoked mid-connection
                            self._active_connections.pop(recipient_id, None)
                            try:
                                recipient_ws.close(4003, "Device revoked")
                            except Exception:
                                pass
        except Exception:
            pass
        finally:
            if registered_device_id:
                with self._lock:
                    if self._active_connections.get(registered_device_id) == websocket:
                        self._active_connections.pop(registered_device_id, None)


__all__ = ["WebSocketRelayServer"]
