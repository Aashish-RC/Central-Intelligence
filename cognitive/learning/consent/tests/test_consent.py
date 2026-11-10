"""Unit tests for Consent & Training-Data Lineage (Features 7.21, 7.22)."""

import pytest
from cognitive.learning.consent.consent_manager import TrainingConsentManager
from cognitive.learning.consent.lineage_tracker import TrainingLineageTracker
from control.safety.consent.c15t_adapter import C15tConsentAdapter, ConsentPurpose


def test_opted_out_users_data_excluded_from_training_datasets():
    c15t = C15tConsentAdapter(default_opt_in=False)
    manager = TrainingConsentManager(c15t_adapter=c15t)

    user_opted_in = "user_agree"
    user_opted_out = "user_refuse"
    user_privacy_mode = "user_private"

    # Grant consent for user_opted_in
    c15t.grant_consent(user_id=user_opted_in, purposes=[ConsentPurpose.MODEL_TRAINING])

    # Explicitly verify user_opted_out has no consent (default False)
    # Put user_privacy_mode into privacy mode
    c15t.set_privacy_mode(user_id=user_privacy_mode, enabled=True)

    dataset = [
        {"id": "sample_1", "user_id": user_opted_in, "prompt": "Fine-tune example 1"},
        {"id": "sample_2", "user_id": user_opted_out, "prompt": "Private conversation of opted out user"},
        {"id": "sample_3", "user_id": user_privacy_mode, "prompt": "Strict private mode conversation"},
        {"id": "sample_4", "user_id": user_opted_in, "prompt": "Fine-tune example 2"},
    ]

    filtered = manager.filter_dataset_by_consent(dataset)

    # Opted-out user's data excluded from training datasets
    assert len(filtered) == 2
    assert all(item["user_id"] == user_opted_in for item in filtered)
    assert not any(item["user_id"] == user_opted_out for item in filtered)
    assert not any(item["user_id"] == user_privacy_mode for item in filtered)


def test_lineage_tracking_verification_and_gdpr_purge():
    tracker = TrainingLineageTracker()

    sample_text = "Optimized mathematical theorem proof."
    prov = tracker.record_provenance(
        example_id="ex_proof_01",
        user_id="researcher_x",
        content=sample_text,
        consent_receipt_hash="hash_receipt_abc123",
        source_session_id="session_math_42",
    )

    assert prov.lineage_signature != ""

    # Verify matching lineage
    assert tracker.verify_lineage("ex_proof_01", sample_text) is True
    # Verify modified content fails lineage
    assert tracker.verify_lineage("ex_proof_01", "Tampered theorem proof.") is False

    # GDPR purge
    purged = tracker.purge_user_data("researcher_x")
    assert "ex_proof_01" in purged
    assert tracker.get_provenance("ex_proof_01") is None
