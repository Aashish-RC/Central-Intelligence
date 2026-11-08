"""
Data models for Remote Access and Cryptographic Device Pairing.
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    DESKTOP = "desktop"
    MOBILE = "mobile"
    LAPTOP = "laptop"
    HEADLESS_SERVER = "headless_server"


class PathType(str, Enum):
    DIRECT_LAN = "direct_lan"
    DIRECT_P2P = "direct_p2p"
    RELAY = "relay"


class DeviceStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PairingCode(BaseModel):
    code: str
    initiator_device_id: str
    initiator_public_key: str
    expires_at: float
    consumed: bool = False


class DeviceRegistration(BaseModel):
    device_id: str
    device_name: str
    device_type: DeviceType = DeviceType.MOBILE
    public_key: str
    ip_address: str = "127.0.0.1"
    status: DeviceStatus = DeviceStatus.ACTIVE
    metadata: Dict[str, Any] = Field(default_factory=dict)
    paired_at: float = Field(default_factory=time.time)
    last_seen_at: float = Field(default_factory=time.time)


class EncryptedFrame(BaseModel):
    frame_id: str = Field(default_factory=lambda: f"frm_{uuid.uuid4().hex[:10]}")
    sender_id: str
    recipient_id: str
    iv_nonce: str  # hex-encoded 12 bytes
    ciphertext: str  # hex-encoded AES-GCM ciphertext + tag
    timestamp: float = Field(default_factory=time.time)
