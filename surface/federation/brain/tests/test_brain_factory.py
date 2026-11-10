"""Unit tests for SpecializedBrainFactory (Task 19.2)."""

import pytest
from surface.federation.brain.brain_factory import (
    SpecializedBrainFactory,
    BrainLifecycleStatus,
)


@pytest.fixture
def factory():
    return SpecializedBrainFactory()


def test_create_legal_brain_with_corpus_persona_compliance_mode(factory: SpecializedBrainFactory):
    """Acceptance test: Can create 'Legal Brain' with legal corpus + persona + compliance mode."""
    corpus = [
        "Delaware General Corporation Law (DGCL)",
        "GDPR Compliance Guidelines & Article 28 DPA",
        "Standard IEEE Software Licensing Precedents",
    ]
    persona = "Strict, citation-mandatory corporate and IP legal counsel"

    legal_brain = factory.create_brain(
        domain="legal",
        name="Legal Brain",
        persona=persona,
        corpus=corpus,
        compliance_mode=True,
    )

    assert legal_brain.name == "Legal Brain"
    assert legal_brain.domain == "legal"
    assert legal_brain.compliance_mode is True
    assert legal_brain.status == BrainLifecycleStatus.ACTIVE
    assert legal_brain.health_score == 1.0
    assert len(legal_brain.domain_corpus) == 3
    assert "DGCL" in legal_brain.domain_corpus[0]
    assert legal_brain.public_key.startswith("pk_")


def test_brain_health_monitoring_and_retirement(factory: SpecializedBrainFactory):
    """Test health score tracking and retirement with archived learnings."""
    brain = factory.create_brain(
        domain="dev",
        name="Dev Brain",
        persona="Senior Rust and distributed systems engineer",
        compliance_mode=False,
    )

    # Monitor health
    health = factory.monitor_brain_health(brain.brain_id, error_rate=0.05)
    assert health == 0.95
    assert brain.status == BrainLifecycleStatus.ACTIVE

    # Degrade health
    degraded = factory.monitor_brain_health(brain.brain_id, error_rate=0.40)
    assert degraded == 0.60
    assert brain.status == BrainLifecycleStatus.DEGRADED

    # Retire brain with archived learnings
    retired = factory.retire_brain(
        brain.brain_id,
        learnings_summary="Accumulated 120 zero-downtime deploy heuristics and CRDT optimizations.",
    )
    assert retired.status == BrainLifecycleStatus.RETIRED
    assert len(retired.archived_learnings) == 1
    assert "CRDT optimizations" in retired.archived_learnings[0]["summary"]
