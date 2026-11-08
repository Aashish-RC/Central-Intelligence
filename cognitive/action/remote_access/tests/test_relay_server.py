"""Tests for X25519 pairing, ChaCha20-Poly1305 E2E encryption, WebSocket relay server, and adaptive path selection."""

import json
import socket
import threading
import time
from typing import Generator
import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from remote_access import (
    AdaptiveRelayChannel,
    DeviceRegistration,
    DeviceStatus,
    DeviceType,
    E2EEncryptedChannel,
    EncryptedFrame,
    PairedDeviceRegistry,
    PathType,
    WebSocketRelayServer,
    generate_wireguard_keys,
    perform_x25519_key_exchange,
)


@pytest.fixture
def relay_env() -> Generator[tuple[WebSocketRelayServer, str, PairedDeviceRegistry], None, None]:
    registry = PairedDeviceRegistry()
    server = WebSocketRelayServer(registry=registry)
    url = server.start("127.0.0.1", 0)
    yield server, url, registry
    server.stop()


def test_real_x25519_key_exchange_derives_shared_secret():
    """Verify that generate_wireguard_keys produces real X25519 keys and ECDH derives identical secrets."""
    priv_a, pub_a = generate_wireguard_keys()
    priv_b, pub_b = generate_wireguard_keys()

    # WireGuard keys are base64-encoded 32-byte keys (44 chars)
    assert len(priv_a) == 44
    assert len(pub_a) == 44
    assert len(priv_b) == 44
    assert len(pub_b) == 44

    # Perform mutual X25519 key exchange
    shared_a = perform_x25519_key_exchange(priv_a, pub_b)
    shared_b = perform_x25519_key_exchange(priv_b, pub_a)

    assert len(shared_a) == 32
    assert shared_a == shared_b


def test_two_local_clients_talk_through_relay(relay_env):
    """Core Spec: Two local clients talk through the WebSocket relay using ChaCha20-Poly1305."""
    server, url, registry = relay_env

    # 1. Generate real X25519 keys and register devices
    priv_a, pub_a = generate_wireguard_keys()
    priv_b, pub_b = generate_wireguard_keys()

    dev_a = DeviceRegistration(
        device_id="client_device_a",
        device_name="Client A",
        device_type=DeviceType.DESKTOP,
        public_key=pub_a,
        status=DeviceStatus.ACTIVE,
    )
    dev_b = DeviceRegistration(
        device_id="client_device_b",
        device_name="Client B",
        device_type=DeviceType.MOBILE,
        public_key=pub_b,
        status=DeviceStatus.ACTIVE,
    )
    registry.register(dev_a)
    registry.register(dev_b)

    # 2. Derive shared secret via X25519 ECDH
    shared_secret = perform_x25519_key_exchange(priv_a, pub_b)
    channel_a = E2EEncryptedChannel(shared_secret, cipher="chacha20")
    channel_b = E2EEncryptedChannel(shared_secret, cipher="chacha20")

    # 3. Connect clients to WebSocket relay
    with connect(url) as ws_a, connect(url) as ws_b:
        # Register on relay
        ws_a.send(json.dumps({"type": "register", "device_id": "client_device_a"}))
        resp_a = json.loads(ws_a.recv())
        assert resp_a["type"] == "registered"

        ws_b.send(json.dumps({"type": "register", "device_id": "client_device_b"}))
        resp_b = json.loads(ws_b.recv())
        assert resp_b["type"] == "registered"

        # 4. Client A encrypts and sends message through relay
        secret_plaintext = b"Pheonix secure command: orchestrate step 32"
        frame_a = channel_a.encrypt(
            secret_plaintext,
            sender_id="client_device_a",
            recipient_id="client_device_b",
        )
        ws_a.send(json.dumps({
            "type": "frame",
            "frame": frame_a.model_dump(),
        }))

        # 5. Client B receives forwarded frame and decrypts
        raw_msg_b = ws_b.recv()
        msg_b = json.loads(raw_msg_b)
        assert msg_b["type"] == "frame"

        received_frame = EncryptedFrame(**msg_b["frame"])
        decrypted_payload = channel_b.decrypt(received_frame)
        assert decrypted_payload == secret_plaintext

        # Verify relay server forwarded counter
        for _ in range(20):
            if server.forwarded_count >= 1:
                break
            time.sleep(0.02)
        assert server.forwarded_count >= 1


def test_relay_never_sees_plaintext(relay_env):
    """Core Spec: The relay server forwards encrypted frames and never sees plaintext."""
    server, url, registry = relay_env

    priv_a, pub_a = generate_wireguard_keys()
    priv_b, pub_b = generate_wireguard_keys()

    registry.register(DeviceRegistration(device_id="dev_1", device_name="D1", public_key=pub_a))
    registry.register(DeviceRegistration(device_id="dev_2", device_name="D2", public_key=pub_b))

    shared_secret = perform_x25519_key_exchange(priv_a, pub_b)
    channel = E2EEncryptedChannel(shared_secret, cipher="chacha20")

    secret_phrase = "UltraConfidentialHumanInstruction998877"
    frame = channel.encrypt(secret_phrase.encode("utf-8"), sender_id="dev_1", recipient_id="dev_2")

    with connect(url) as ws_1, connect(url) as ws_2:
        ws_1.send(json.dumps({"type": "register", "device_id": "dev_1"}))
        ws_1.recv()
        ws_2.send(json.dumps({"type": "register", "device_id": "dev_2"}))
        ws_2.recv()

        ws_1.send(json.dumps({"type": "frame", "frame": frame.model_dump()}))
        ws_2.recv()

    # Inspect all records preserved on the relay server
    assert len(server.recorded_relay_payloads) > 0
    for payload in server.recorded_relay_payloads:
        assert secret_phrase not in payload
        assert "UltraConfidential" not in payload
        # Only hex ciphertext and metadata present
        assert frame.ciphertext in payload


def test_unpaired_client_is_rejected(relay_env):
    """Core Spec: An unpaired/unauthorized client attempting to register is rejected."""
    server, url, registry = relay_env

    with connect(url) as ws_attacker:
        ws_attacker.send(json.dumps({
            "type": "register",
            "device_id": "unpaired_rogue_device",
        }))

        # Server responds with error and closes connection
        try:
            resp = json.loads(ws_attacker.recv())
            assert resp["type"] == "error"
            assert "unauthorized" in resp["message"].lower() or "unpaired" in resp["message"].lower()
        except ConnectionClosed:
            pass  # closed immediately with 4003

    assert server.rejected_count >= 1


def test_revoking_device_ends_session_mid_connection(relay_env):
    """Core Spec: Revoking a device ends its session mid-connection."""
    server, url, registry = relay_env

    registry.register(DeviceRegistration(device_id="dev_alice", device_name="Alice", public_key="pk_alice"))
    registry.register(DeviceRegistration(device_id="dev_bob", device_name="Bob", public_key="pk_bob"))

    with connect(url) as ws_alice, connect(url) as ws_bob:
        ws_alice.send(json.dumps({"type": "register", "device_id": "dev_alice"}))
        assert json.loads(ws_alice.recv())["type"] == "registered"

        ws_bob.send(json.dumps({"type": "register", "device_id": "dev_bob"}))
        assert json.loads(ws_bob.recv())["type"] == "registered"

        # Now revoke Bob mid-connection
        server.revoke_device("dev_bob")
        assert registry.is_authorized("dev_bob") is False

        # Attempting to send from Bob now must fail or connection is closed
        with pytest.raises(ConnectionClosed):
            ws_bob.send(json.dumps({
                "type": "frame",
                "frame": {
                    "sender_id": "dev_bob",
                    "recipient_id": "dev_alice",
                    "iv_nonce": "aa" * 12,
                    "ciphertext": "bb" * 16,
                },
            }))
            ws_bob.recv()

        # Alice sending to revoked Bob is rejected
        ws_alice.send(json.dumps({
            "type": "frame",
            "frame": {
                "sender_id": "dev_alice",
                "recipient_id": "dev_bob",
                "iv_nonce": "aa" * 12,
                "ciphertext": "bb" * 16,
            },
        }))
        resp = json.loads(ws_alice.recv())
        assert resp["type"] == "error"
        assert "unauthorized or revoked" in resp["message"].lower()


def test_tampered_messages_are_rejected():
    """Core Spec: Tampered messages fail ChaCha20-Poly1305 authentication and are rejected."""
    shared_secret = b"tamper_verification_shared_secret_32"
    channel = E2EEncryptedChannel(shared_secret, cipher="chacha20")

    original_message = b"Legitimate financial payment authorization"
    frame = channel.encrypt(original_message, sender_id="user_1", recipient_id="agent_1")

    # 1. Normal decrypt succeeds
    assert channel.decrypt(frame) == original_message

    # 2. Tampered ciphertext byte fails Poly1305 authentication tag
    raw_ct = bytearray(bytes.fromhex(frame.ciphertext))
    raw_ct[0] ^= 0x01
    tampered_frame = EncryptedFrame(
        frame_id=frame.frame_id,
        sender_id=frame.sender_id,
        recipient_id=frame.recipient_id,
        iv_nonce=frame.iv_nonce,
        ciphertext=raw_ct.hex(),
    )

    with pytest.raises(ValueError, match="cryptographic authentication failed"):
        channel.decrypt(tampered_frame)

    # 3. Tampered nonce also fails
    raw_nonce = bytearray(bytes.fromhex(frame.iv_nonce))
    raw_nonce[0] ^= 0x01
    tampered_nonce_frame = EncryptedFrame(
        frame_id=frame.frame_id,
        sender_id=frame.sender_id,
        recipient_id=frame.recipient_id,
        iv_nonce=raw_nonce.hex(),
        ciphertext=frame.ciphertext,
    )

    with pytest.raises(ValueError, match="cryptographic authentication failed"):
        channel.decrypt(tampered_nonce_frame)


def test_path_selection_tcp_first_then_lan_then_relay():
    """Core Spec: Path selection tries real direct TCP connection first, then LAN, then relay."""
    channel = AdaptiveRelayChannel()

    # 1. When a real direct TCP port is listening on host_ip, direct TCP succeeds
    dummy_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    dummy_server.bind(("127.0.0.1", 0))
    dummy_server.listen(1)
    tcp_port = dummy_server.getsockname()[1]

    try:
        path, reason = channel.probe_and_select_path(
            host_ip="127.0.0.1",
            client_ip="10.200.0.5",  # different subnet
            host_port=tcp_port,
        )
        assert path == PathType.DIRECT_P2P
        assert "Direct TCP connection established" in reason
    finally:
        dummy_server.close()

    # 2. When direct TCP is not listening, but IP is on local LAN subnet
    path_lan, reason_lan = channel.probe_and_select_path(
        host_ip="192.168.1.50",
        client_ip="192.168.1.100",
        host_port=59999,  # nothing listening
        timeout=0.05,
    )
    assert path_lan == PathType.DIRECT_LAN
    assert "Local subnet match confirmed" in reason_lan

    # 3. When direct TCP fails and IP is not local LAN, falls back to relay
    path_relay, reason_relay = channel.probe_and_select_path(
        host_ip="198.51.100.5",
        client_ip="203.0.113.10",
        host_port=59999,
        timeout=0.05,
    )
    assert path_relay == PathType.RELAY
    assert "NAT traversal failed" in reason_relay
