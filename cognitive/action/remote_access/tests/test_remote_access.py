"""
Comprehensive automated test suite for Remote Access & Pairing (Step 32).
"""
import pytest
import time
from remote_access.core.crypto_channel import E2EEncryptedChannel
from remote_access.core.device_registry import PairedDeviceRegistry
from remote_access.core.models import (
    DeviceRegistration,
    DeviceStatus,
    DeviceType,
    EncryptedFrame,
    PathType,
)
from remote_access.core.pairing import PairingCoordinator
from remote_access.core.path_selector import PathSelector
from remote_access.relay.relay_service import EncryptedRelayRouter


def test_pairing_code_generation_and_expiry():
    coordinator = PairingCoordinator(code_ttl_seconds=0.1)

    code = coordinator.generate_pairing_code("host_desktop_1", "pubkey_host_xyz")
    assert len(code.code) == 6
    assert code.code.isdigit()
    assert code.consumed is False

    # Wait for TTL expiry
    time.sleep(0.15)
    with pytest.raises(ValueError, match="expired"):
        coordinator.redeem_pairing_code(
            code.code,
            "client_mobile_1",
            "Aashish Phone",
            DeviceType.MOBILE,
            "pubkey_client_abc",
        )


def test_pairing_code_single_use_consumed():
    coordinator = PairingCoordinator(code_ttl_seconds=60.0)

    code = coordinator.generate_pairing_code("host_desktop_1", "pubkey_host_xyz")

    # First redemption succeeds
    reg, secret = coordinator.redeem_pairing_code(
        code.code,
        "client_mobile_1",
        "Aashish Phone",
        DeviceType.MOBILE,
        "pubkey_client_abc",
    )
    assert reg.device_id == "client_mobile_1"
    assert reg.status == DeviceStatus.ACTIVE
    assert len(secret) > 0

    # Second redemption must fail
    with pytest.raises(ValueError, match="Invalid pairing code"):
        coordinator.redeem_pairing_code(
            code.code,
            "client_mobile_2",
            "Attacker Phone",
            DeviceType.MOBILE,
            "pubkey_attacker",
        )


def test_e2e_encryption_and_decryption():
    shared_secret = b"cryptographic_shared_pairing_secret_12345678"
    host_channel = E2EEncryptedChannel(shared_secret)
    client_channel = E2EEncryptedChannel(shared_secret)

    plaintext = b"Pheonix remote access prompt: summarize recent orchestrator logs"
    frame = host_channel.encrypt(plaintext, sender_id="host_1", recipient_id="client_1")

    assert frame.sender_id == "host_1"
    assert frame.recipient_id == "client_1"
    assert len(frame.ciphertext) > 0
    assert len(frame.iv_nonce) == 24  # 12 bytes hex

    decrypted = client_channel.decrypt(frame)
    assert decrypted == plaintext


def test_e2e_tamper_proofing():
    shared_secret = b"tamper_test_secret_entropy_87654321"
    channel = E2EEncryptedChannel(shared_secret)

    frame = channel.encrypt(b"Sensitive payload", sender_id="device_a", recipient_id="device_b")

    # Tamper with ciphertext
    raw_ct = list(bytes.fromhex(frame.ciphertext))
    raw_ct[0] ^= 0xFF  # flip byte
    tampered_frame = EncryptedFrame(
        frame_id=frame.frame_id,
        sender_id=frame.sender_id,
        recipient_id=frame.recipient_id,
        iv_nonce=frame.iv_nonce,
        ciphertext=bytes(raw_ct).hex(),
    )

    with pytest.raises(ValueError, match="cryptographic authentication failed"):
        channel.decrypt(tampered_frame)


def test_paired_device_registry_authorization():
    registry = PairedDeviceRegistry()

    dev = DeviceRegistration(
        device_id="phone_001",
        device_name="Pixel 9 Pro",
        device_type=DeviceType.MOBILE,
        public_key="pub_pixel_123",
        status=DeviceStatus.ACTIVE,
    )
    registry.register(dev)

    assert registry.is_authorized("phone_001") is True
    assert registry.is_authorized("unknown_device") is False

    # Revoke access
    revoked = registry.revoke("phone_001")
    assert revoked is True
    assert registry.is_authorized("phone_001") is False


def test_path_selector_local_vs_relay():
    selector = PathSelector()

    # Loopback
    path1, _ = selector.select_path("127.0.0.1", "127.0.0.1")
    assert path1 == PathType.DIRECT_LAN

    # Same private subnet
    path2, _ = selector.select_path("192.168.1.50", "192.168.1.120")
    assert path2 == PathType.DIRECT_LAN

    # Cross subnet / Public IPs
    path3, _ = selector.select_path("192.168.1.50", "10.0.4.15")
    assert path3 == PathType.RELAY

    # Forced relay
    path4, _ = selector.select_path("192.168.1.50", "192.168.1.51", force_relay=True)
    assert path4 == PathType.RELAY


def test_encrypted_relay_forwarding_zero_knowledge():
    registry = PairedDeviceRegistry()
    relay = EncryptedRelayRouter(registry=registry)

    dev_a = DeviceRegistration(device_id="dev_a", device_name="Dev A", public_key="pk_a")
    dev_b = DeviceRegistration(device_id="dev_b", device_name="Dev B", public_key="pk_b")
    registry.register(dev_a)
    registry.register(dev_b)

    frame = EncryptedFrame(
        sender_id="dev_a",
        recipient_id="dev_b",
        iv_nonce="12" * 12,
        ciphertext="abcd" * 10,
    )

    # Route frame
    routed = relay.route_frame(frame)
    assert routed is True
    assert relay.forwarded_count == 1

    # Dev B receives frame
    received = relay.receive_frames("dev_b")
    assert len(received) == 1
    assert received[0].frame_id == frame.frame_id
    assert received[0].ciphertext == frame.ciphertext

    # Second drain is empty
    assert len(relay.receive_frames("dev_b")) == 0

    # Unauthorized sender or recipient rejected
    bad_frame = EncryptedFrame(
        sender_id="hacker_x",
        recipient_id="dev_b",
        iv_nonce="12" * 12,
        ciphertext="ffff" * 10,
    )
    assert relay.route_frame(bad_frame) is False
