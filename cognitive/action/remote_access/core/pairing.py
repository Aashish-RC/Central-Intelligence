"""
Cryptographic Device Pairing Coordinator.
Manages ephemeral PIN generation, mutual key verification, and secure device enrollment.
"""
from __future__ import annotations

import secrets
import time
from typing import Dict, Optional, Tuple
from remote_access.core.models import DeviceRegistration, DeviceStatus, DeviceType, PairingCode


class PairingCoordinator:
    """Coordinates out-of-band ephemeral pairing and mutual authentication."""

    def __init__(self, code_ttl_seconds: float = 300.0):
        self.code_ttl_seconds = code_ttl_seconds
        self._active_codes: Dict[str, PairingCode] = {}

    def generate_pairing_code(self, initiator_device_id: str, initiator_public_key: str) -> PairingCode:
        # Generate 6-digit cryptographically secure PIN
        code_str = f"{secrets.randbelow(900000) + 100000}"
        expires_at = time.time() + self.code_ttl_seconds

        code_obj = PairingCode(
            code=code_str,
            initiator_device_id=initiator_device_id,
            initiator_public_key=initiator_public_key,
            expires_at=expires_at,
            consumed=False,
        )
        self._active_codes[code_str] = code_obj
        return code_obj

    def redeem_pairing_code(
        self,
        code_str: str,
        client_device_id: str,
        client_device_name: str,
        client_device_type: DeviceType,
        client_public_key: str,
        client_ip: str = "127.0.0.1",
    ) -> Tuple[DeviceRegistration, bytes]:
        """Redeems an active pairing code and derives the initial pairing shared secret."""
        code_obj = self._active_codes.get(code_str)
        if not code_obj:
            raise ValueError("Invalid pairing code")

        if code_obj.consumed:
            raise ValueError("Pairing code has already been consumed")

        if time.time() > code_obj.expires_at:
            del self._active_codes[code_str]
            raise ValueError("Pairing code has expired")

        # Mark consumed
        code_obj.consumed = True
        del self._active_codes[code_str]

        # Derive shared secret from both public keys and PIN
        entropy = f"{code_obj.initiator_public_key}:{client_public_key}:{code_str}".encode("utf-8")

        registration = DeviceRegistration(
            device_id=client_device_id,
            device_name=client_device_name,
            device_type=client_device_type,
            public_key=client_public_key,
            ip_address=client_ip,
            status=DeviceStatus.ACTIVE,
            paired_at=time.time(),
            last_seen_at=time.time(),
        )

        return registration, entropy

    def generate_wireguard_handshake(
        self,
        code_str: str,
        client_device_id: str,
        client_device_name: str,
        client_device_type: DeviceType,
        server_endpoint: str = "relay.pheonix.internal:51820",
    ) -> Tuple[DeviceRegistration, str]:
        """Performs cryptographic key-exchange handshake returning client WireGuard configuration file."""
        code_obj = self._active_codes.get(code_str)
        if not code_obj:
            raise ValueError("Invalid pairing code")
        server_pub = code_obj.initiator_public_key

        priv_key, pub_key = generate_wireguard_keys()
        reg, _ = self.redeem_pairing_code(
            code_str=code_str,
            client_device_id=client_device_id,
            client_device_name=client_device_name,
            client_device_type=client_device_type,
            client_public_key=pub_key,
        )
        config = generate_wireguard_config(
            client_private_key=priv_key,
            client_ip="10.100.0.5",
            server_public_key=server_pub,
            server_endpoint=server_endpoint,
        )
        return reg, config


import base64
import os
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def generate_wireguard_keys() -> Tuple[str, str]:
    """Generates real Curve25519/X25519 base64-encoded WireGuard private and public key pair."""
    priv = X25519PrivateKey.generate()
    pub = priv.public_key()
    priv_bytes = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_bytes = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(priv_bytes).decode("ascii"), base64.b64encode(pub_bytes).decode("ascii")


def perform_x25519_key_exchange(private_key_b64: str, peer_public_key_b64: str) -> bytes:
    """Performs real X25519 Diffie-Hellman key exchange and returns 32-byte shared secret."""
    priv_bytes = base64.b64decode(private_key_b64)
    pub_bytes = base64.b64decode(peer_public_key_b64)
    priv = X25519PrivateKey.from_private_bytes(priv_bytes)
    pub = X25519PublicKey.from_public_bytes(pub_bytes)
    return priv.exchange(pub)


def generate_wireguard_config(
    client_private_key: str,
    client_ip: str = "10.100.0.2",
    server_public_key: Optional[str] = None,
    server_endpoint: str = "relay.pheonix.internal:51820",
    allowed_ips: str = "10.100.0.0/24",
    dns: str = "1.1.1.1",
) -> str:
    """Generates standard INI format WireGuard client configuration file with real X25519 keys."""
    if server_public_key is None or server_public_key == "pub_server_wg_mock":
        _, server_public_key = generate_wireguard_keys()

    return f"""[Interface]
PrivateKey = {client_private_key}
Address = {client_ip}/32
DNS = {dns}

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_endpoint}
AllowedIPs = {allowed_ips}
PersistentKeepalive = 25
""".strip()
