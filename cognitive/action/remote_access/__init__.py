"""
Pheonix Remote Access and Device Pairing Subsystem (Wave 8, Step 32).
"""
from remote_access.core.crypto_channel import E2EEncryptedChannel
from remote_access.core.device_registry import PairedDeviceRegistry
from remote_access.core.models import (
    DeviceRegistration,
    DeviceStatus,
    DeviceType,
    EncryptedFrame,
    PairingCode,
    PathType,
)
from remote_access.core.pairing import (
    PairingCoordinator,
    generate_wireguard_keys,
    generate_wireguard_config,
    perform_x25519_key_exchange,
)
from remote_access.core.path_selector import PathSelector
from remote_access.core.relay import AdaptiveRelayChannel
from remote_access.relay.relay_service import EncryptedRelayRouter
from remote_access.relay_server import WebSocketRelayServer

__all__ = [
    "DeviceType",
    "PathType",
    "DeviceStatus",
    "PairingCode",
    "DeviceRegistration",
    "EncryptedFrame",
    "PairingCoordinator",
    "generate_wireguard_keys",
    "generate_wireguard_config",
    "perform_x25519_key_exchange",
    "E2EEncryptedChannel",
    "PairedDeviceRegistry",
    "PathSelector",
    "AdaptiveRelayChannel",
    "EncryptedRelayRouter",
    "WebSocketRelayServer",
]
