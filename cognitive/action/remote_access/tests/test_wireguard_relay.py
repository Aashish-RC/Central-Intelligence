"""Unit tests for WireGuard configuration generation and NAT failure relay fallback."""

import pytest
from remote_access import (
    AdaptiveRelayChannel,
    DeviceRegistration,
    DeviceType,
    EncryptedFrame,
    PairingCoordinator,
    PathType,
    generate_wireguard_config,
    generate_wireguard_keys,
)


def test_wireguard_handshake_and_config_generation():
    coordinator = PairingCoordinator(code_ttl_seconds=60.0)
    server_pub = "pub_server_wireguard_key_xyz123=="
    code_obj = coordinator.generate_pairing_code("server_box", server_pub)

    reg, wg_config = coordinator.generate_wireguard_handshake(
        code_str=code_obj.code,
        client_device_id="client_phone_001",
        client_device_name="Pixel 9",
        client_device_type=DeviceType.MOBILE,
        server_endpoint="vpn.pheonix.org:51820",
    )

    assert reg.device_id == "client_phone_001"
    assert "[Interface]" in wg_config
    assert "PrivateKey = " in wg_config
    assert "Address = 10.100.0.5/32" in wg_config
    assert "[Peer]" in wg_config
    assert f"PublicKey = {server_pub}" in wg_config
    assert "Endpoint = vpn.pheonix.org:51820" in wg_config
    assert "PersistentKeepalive = 25" in wg_config


def test_adaptive_relay_path_direct_p2p():
    channel = AdaptiveRelayChannel()
    path, reason = channel.probe_and_select_path(
        host_ip="198.51.100.1",
        client_ip="203.0.113.5",
        direct_probe_fn=lambda: True,
    )
    assert path == PathType.DIRECT_P2P
    assert "Direct P2P socket established" in reason


def test_adaptive_relay_path_lan_probe():
    channel = AdaptiveRelayChannel()
    path, reason = channel.probe_and_select_path(
        host_ip="192.168.1.10",
        client_ip="192.168.1.50",
        direct_probe_fn=lambda: False,
        lan_probe_fn=lambda: True,
    )
    assert path == PathType.DIRECT_LAN
    assert "Local LAN ping succeeded" in reason


def test_nat_failure_transparent_fallback_to_relay():
    """Core Done When Criteria: Simulate NAT failure and verify transparent fallback to the relay channel."""
    channel = AdaptiveRelayChannel()

    # Simulate NAT failure: direct P2P fails (symmetric NAT) and LAN ping fails (different remote networks)
    path, reason = channel.probe_and_select_path(
        host_ip="198.51.100.10",
        client_ip="203.0.113.20",
        direct_probe_fn=lambda: False,  # STUN/P2P hole-punch failed
        lan_probe_fn=lambda: False,     # Not on same local subnet
    )

    assert path == PathType.RELAY
    assert "NAT traversal failed" in reason
    assert "transparent fallback to WebSocket encrypted relay" in reason
