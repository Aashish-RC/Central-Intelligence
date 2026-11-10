"""Unit tests for FederatedBrainSync Protocol Crown Jewel (Task 19.3)."""

import pytest
from surface.federation.brain.brain_factory import SpecializedBrain
from surface.federation.sync.consent_gate import ConsentDeniedError, ConsentGate
from surface.federation.sync.conflict_resolver import BrainConflictResolver
from surface.federation.sync.federated_sync import (
    FederatedBrainSync,
    FederatedDataPayload,
)


@pytest.fixture
def sync_protocol():
    consent = ConsentGate()
    resolver = BrainConflictResolver()
    return FederatedBrainSync(consent_gate=consent, conflict_resolver=resolver)


@pytest.fixture
def legal_brain():
    return SpecializedBrain(
        brain_id="brain_legal_01",
        name="Legal Brain",
        domain="legal",
        persona="Corporate IP and Compliance Counsel",
        public_key="pk_legal_rsa_9999",
    )


@pytest.fixture
def dev_brain():
    return SpecializedBrain(
        brain_id="brain_dev_02",
        name="Dev Brain",
        domain="software_engineering",
        persona="Lead Systems Architect",
        public_key="pk_dev_rsa_8888",
    )


def test_legal_brain_sends_verified_output_to_dev_brain_via_encrypted_channel(
    sync_protocol: FederatedBrainSync,
    legal_brain: SpecializedBrain,
    dev_brain: SpecializedBrain,
):
    """Acceptance test: Legal Brain sends verified output to Dev Brain via encrypted channel; Dev Brain receives + verifies."""
    data = FederatedDataPayload(
        data_id="licensing_spec_v1",
        data_type="compliance_rules",
        version=1,
        payload={
            "license": "Apache-2.0",
            "required_notices": ["Notice of Copyright 2026 Central Intelligence"],
            "allow_commercial_use": True,
        },
        sender_brain_id=legal_brain.brain_id,
    )

    # Push from Legal Brain -> Dev Brain
    envelope = sync_protocol.push(
        sender_brain=legal_brain,
        receiver_brain=dev_brain,
        data=data,
    )

    # Verify encrypted envelope was produced
    assert envelope.envelope_id.startswith("env_")
    assert envelope.sender_id == legal_brain.brain_id
    assert envelope.recipient_id == dev_brain.public_key
    assert len(envelope.ciphertext_base64) > 0
    assert len(envelope.signature) > 0

    # Verify Dev Brain successfully decrypted, verified signature, and ingested data
    ingested = sync_protocol.get_brain_data(dev_brain.brain_id, "licensing_spec_v1")
    assert ingested is not None
    assert ingested.payload["license"] == "Apache-2.0"
    assert ingested.sender_brain_id == legal_brain.brain_id
    assert ingested.signature is not None


def test_pull_sync_requires_consent_gate(
    sync_protocol: FederatedBrainSync,
    legal_brain: SpecializedBrain,
    dev_brain: SpecializedBrain,
):
    """Pull sync is blocked if user has not granted consent for the brain and data type."""
    # Seed data on Legal Brain store
    data = FederatedDataPayload(
        data_id="privilege_memo_101",
        data_type="privileged_legal_memo",
        version=1,
        payload={"strategy": "Acquisition antitrust clearance details"},
        sender_brain_id=legal_brain.brain_id,
    )
    sync_protocol._get_store(legal_brain.brain_id)["privilege_memo_101"] = data

    # 1. Dev Brain attempts to pull without consent -> raises ConsentDeniedError
    with pytest.raises(ConsentDeniedError, match="User has not consented"):
        sync_protocol.pull(
            source_brain=legal_brain,
            target_brain=dev_brain,
            data_id="privilege_memo_101",
            data_type="privileged_legal_memo",
        )

    # 2. Grant explicit consent
    sync_protocol.consent.grant_consent(legal_brain.brain_id, "privileged_legal_memo")

    # 3. Pull succeeds and is verified
    pulled = sync_protocol.pull(
        source_brain=legal_brain,
        target_brain=dev_brain,
        data_id="privilege_memo_101",
        data_type="privileged_legal_memo",
    )
    assert pulled.data_id == "privilege_memo_101"
    assert pulled.payload["strategy"] == "Acquisition antitrust clearance details"


def test_version_conflict_resolution(
    sync_protocol: FederatedBrainSync,
    legal_brain: SpecializedBrain,
    dev_brain: SpecializedBrain,
):
    """When concurrent updates occur, highest version number wins."""
    # Seed version 1 on Dev Brain
    v1 = FederatedDataPayload(
        data_id="api_spec_001",
        data_type="architecture",
        version=1,
        payload={"spec": "v1 REST API"},
        sender_brain_id=dev_brain.brain_id,
    )
    sync_protocol._get_store(dev_brain.brain_id)["api_spec_001"] = v1

    # Legal brain sends updated version 2
    v2 = FederatedDataPayload(
        data_id="api_spec_001",
        data_type="architecture",
        version=2,
        payload={"spec": "v2 gRPC + REST API with RLS"},
        sender_brain_id=legal_brain.brain_id,
    )
    sync_protocol.push(legal_brain, dev_brain, v2)

    # Resulting record in Dev Brain must be v2
    resolved = sync_protocol.get_brain_data(dev_brain.brain_id, "api_spec_001")
    assert resolved is not None
    assert resolved.version == 2
    assert resolved.payload["spec"] == "v2 gRPC + REST API with RLS"

