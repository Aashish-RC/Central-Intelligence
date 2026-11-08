"""Unit tests for Source-Support and Hallucination Verification."""

import pytest
from web_search.core.models import ScrapedPage, utc_now
from web_search.verifier.claim_checker import SourceSupportVerifier


@pytest.fixture
def verifier():
    return SourceSupportVerifier()


@pytest.fixture
def sample_page():
    clean_text = (
        "NIST SP 800-38D specifies Galois/Counter Mode (GCM) for authenticated encryption with AES-256. "
        "It provides both data confidentiality and authenticity assurance using an authentication tag. "
        "The standard requires a unique initialization vector for every encryption operation under a given key."
    )
    return ScrapedPage(
        url="https://csrc.nist.gov/sp800-38d",
        title="Galois/Counter Mode (GCM) Specification",
        markdown_content=clean_text,
        clean_text=clean_text,
        content_sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        retrieved_at=utc_now(),
    )


def test_supported_claim_verification(verifier, sample_page):
    claim = "NIST SP 800-38D specifies Galois/Counter Mode for authenticated encryption with AES-256."
    res = verifier.verify_claim(claim=claim, source=sample_page, threshold=0.65)

    assert res.is_supported is True
    assert res.support_score >= 0.65
    assert res.supporting_quote is not None
    assert "NIST SP 800-38D specifies Galois/Counter Mode" in res.supporting_quote
    assert res.citation is not None
    assert res.citation.url == sample_page.url


def test_unsupported_hallucinated_claim(verifier, sample_page):
    claim = "AES-256-GCM uses a quantum key exchange protocol based on lattice cryptography."
    res = verifier.verify_claim(claim=claim, source=sample_page, threshold=0.65)

    assert res.is_supported is False
    assert res.support_score < 0.65
    assert res.citation is None
