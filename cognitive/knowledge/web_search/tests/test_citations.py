"""Unit tests for verifiable structured citations."""

import pytest
from web_search.core.models import ScrapedPage, utc_now
from web_search.verifier.claim_checker import SourceSupportVerifier


def test_verifiable_citation_attributes():
    verifier = SourceSupportVerifier()
    content = "FastAPI uses Pydantic models for request validation and serialization."
    page = ScrapedPage(
        url="https://fastapi.tiangolo.com/tutorial/",
        title="FastAPI Tutorial Documentation",
        markdown_content=content,
        clean_text=content,
        content_sha256="deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678",
        retrieved_at=utc_now(),
    )

    claim = "FastAPI uses Pydantic for validation."
    check = verifier.verify_claim(claim=claim, source=page)

    assert check.is_supported is True
    assert check.citation is not None
    cit = check.citation

    assert cit.url == "https://fastapi.tiangolo.com/tutorial/"
    assert cit.domain == "fastapi.tiangolo.com"
    assert cit.title == "FastAPI Tutorial Documentation"
    assert "FastAPI uses Pydantic models" in cit.quote_text
    assert cit.content_sha256 == page.content_sha256
    assert cit.retrieved_at is not None
