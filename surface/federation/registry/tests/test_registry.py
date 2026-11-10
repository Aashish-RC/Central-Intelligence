"""Unit tests for SkillPackRegistry (Task 19.4)."""

import pytest
from surface.federation.registry.skill_pack_registry import (
    SkillPackRegistry,
    SkillPackManifest,
    PackStatus,
)


@pytest.fixture
def registry():
    return SkillPackRegistry()


def test_register_healthcare_pack_sandboxed_and_revocation(registry: SkillPackRegistry):
    """Acceptance test: Can register Healthcare pack; pack sandboxed; can revoke."""
    manifest = SkillPackManifest(
        pack_id="pack_healthcare_hipaa_v1",
        name="Healthcare & HIPAA Clinical Assistant Pack",
        domain="healthcare",
        version="1.0.4",
        author="Verified Healthcare AI Consortium",
        skills=["icd10_lookup", "hipaa_phi_sanitizer", "clinical_trial_matcher"],
        permissions={"read_memory", "domain_rag"},
    )

    # 1. Register Healthcare pack
    registered = registry.register_pack(manifest)
    assert registered.pack_id == "pack_healthcare_hipaa_v1"
    assert registered.status == PackStatus.ACTIVE
    assert registered.is_sandboxed is True
    assert registry.is_executable(registered.pack_id) is True

    # 2. Revoke Healthcare pack
    revoked = registry.revoke_pack(registered.pack_id, reason="Policy updated to v2 requirements")
    assert revoked.status == PackStatus.REVOKED
    assert registry.is_executable(registered.pack_id) is False
    assert "Policy updated" in (revoked.quarantine_reason or "")


def test_malicious_unauthorized_pack_quarantined(registry: SkillPackRegistry):
    """Pack requesting unauthorized host privileges is rejected and quarantined."""
    malicious = SkillPackManifest(
        pack_id="pack_suspicious_trojan",
        name="Trojan Pack",
        domain="finance",
        version="0.0.1",
        author="Unknown",
        permissions={"read_memory", "execute_arbitrary_root_shell"},  # Unauthorized!
    )

    with pytest.raises(PermissionError, match="quarantined"):
        registry.register_pack(malicious)

    assert registry.is_executable("pack_suspicious_trojan") is False
    stored = registry.get_pack("pack_suspicious_trojan")
    assert stored is not None
    assert stored.status == PackStatus.QUARANTINED
