"""
Tests for Third-Party Data Minimizer (Features 10.58, 10.59).
"""

import pytest
from control.safety.privacy.third_party_minimizer import (
    MinimizationResult,
    ThirdPartyDataMinimizer,
    default_third_party_minimizer,
)


def test_uploaded_doc_with_third_party_emails_redacted_before_indexing():
    """
    Acceptance criterion: Uploaded doc with third-party emails -> emails redacted before indexing.
    """
    minimizer = ThirdPartyDataMinimizer(preserve_primary_user=True)

    uploaded_doc = (
        "Meeting minutes regarding contract renewal:\n"
        "Lead negotiator: user_john@corp.com\n"
        "External vendor representative: alice.smith@vendor-partner.org\n"
        "Auditor contact: audit-lead@consulting-agency.com\n"
        "Agreed milestones will commence next month."
    )

    # Sanitize doc before L3 indexing, preserving the authenticated user's own email
    res = minimizer.sanitize_for_indexing(
        doc_content=uploaded_doc,
        primary_user_email="user_john@corp.com",
    )

    assert res.has_third_party_pii is True
    assert res.total_redacted == 2

    # Check that third-party emails were redacted
    assert "alice.smith@vendor-partner.org" not in res.sanitized_text
    assert "audit-lead@consulting-agency.com" not in res.sanitized_text
    assert "[REDACTED_THIRD_PARTY_EMAIL]" in res.sanitized_text

    # Check that primary user's email was preserved
    assert "user_john@corp.com" in res.sanitized_text
    assert res.stage == "L3_rag_indexing"


def test_third_party_phone_and_ssn_redaction():
    minimizer = ThirdPartyDataMinimizer()
    text = (
        "Customer file update:\n"
        "Secondary contact phone: 415-555-2671\n"
        "Co-signer SSN: 123-45-6789\n"
        "Credit card on file: 4111111111111111"
    )

    res = minimizer.minimize(text)
    assert res.has_third_party_pii is True
    assert "415-555-2671" not in res.sanitized_text
    assert "123-45-6789" not in res.sanitized_text
    assert "4111111111111111" not in res.sanitized_text
    assert "[REDACTED_THIRD_PARTY_PHONE]" in res.sanitized_text
    assert "[REDACTED_THIRD_PARTY_ID]" in res.sanitized_text
    assert "[REDACTED_THIRD_PARTY_PAYMENT]" in res.sanitized_text


def test_third_party_name_redaction_in_document():
    minimizer = ThirdPartyDataMinimizer()
    text = (
        "Case Summary:\n"
        "Patient Name: Johnathan Doe\n"
        "Witness: Marcus Aurelius Vance\n"
        "Primary diagnosis is stable."
    )

    res = minimizer.minimize(text)
    assert "Johnathan Doe" not in res.sanitized_text
    assert "Marcus Aurelius Vance" not in res.sanitized_text
    assert "[REDACTED_THIRD_PARTY_NAME]" in res.sanitized_text
    assert "Primary diagnosis is stable." in res.sanitized_text


def test_clean_document_without_third_party_pii():
    minimizer = ThirdPartyDataMinimizer()
    text = "The quick brown fox jumps over the lazy dog. System load is nominal."
    res = minimizer.minimize(text)

    assert res.has_third_party_pii is False
    assert res.total_redacted == 0
    assert res.sanitized_text == text


def test_pipeline_stages_helper_methods():
    minimizer = ThirdPartyDataMinimizer()
    sample = "Contact person: candidate@external.org, tel: 212-555-0199"

    # L1 Input Gateway
    r1 = minimizer.scan_input(sample)
    assert r1.stage == "L1_input_gateway"
    assert r1.has_third_party_pii is True

    # L2 Storage
    r2 = minimizer.sanitize_for_storage(sample)
    assert r2.stage == "L2_memory_store"
    assert r2.has_third_party_pii is True

    # L4 Model Context
    r4 = minimizer.sanitize_for_model(sample)
    assert r4.stage == "L4_model_dispatch"
    assert r4.has_third_party_pii is True


def test_whitelist_allows_authorized_third_party_emails():
    minimizer = ThirdPartyDataMinimizer()
    text = "Emails: vendor@partner.org and rogue@unknown.org"
    whitelist = {"vendor@partner.org"}

    res = minimizer.minimize(text, whitelist_emails=whitelist)
    assert "vendor@partner.org" in res.sanitized_text
    assert "rogue@unknown.org" not in res.sanitized_text
    assert res.total_redacted == 1
