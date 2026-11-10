"""
Tests for Content Rights Enforcer & Source Attribution (Features 10.56, 10.57).
"""

import pytest
from control.safety.rights.content_rights import (
    ContentRightsEnforcer,
    default_content_rights_enforcer,
)
from control.safety.guardrails.core.output_guard import OutputGuard
from control.safety.guardrails.client import GuardrailsClient


def test_verbatim_copyright_reproduction_detected_and_redacted():
    enforcer = ContentRightsEnforcer(min_verbatim_words=6)

    # Register proprietary material
    enforcer.register_protected_material(
        material_id="novel_hp_01",
        title="The Secret of the Phoenix Stone",
        holder="Global Publications Ltd",
        text_sample="The grandfather clock struck midnight with a hollow chime that echoed through the empty marble corridors.",
    )

    # Model output that reproduces verbatim passage
    output = "Here is what happened: The grandfather clock struck midnight with a hollow chime that echoed through the empty marble corridors. Then she fled."

    result = enforcer.evaluate_output(output)
    assert not result.is_safe
    assert result.action in ["redact", "redact_and_attribute"]
    assert len(result.infringements) == 1
    assert result.infringements[0].title == "The Secret of the Phoenix Stone"

    # Verify that verbatim passage was redacted
    assert "marble corridors" not in result.sanitized_output
    assert "[REDACTED: Verbatim Copyrighted Material from 'The Secret of the Phoenix Stone' by Global Publications Ltd]" in result.sanitized_output
    assert "Then she fled." in result.sanitized_output


def test_clean_output_without_infringement():
    enforcer = ContentRightsEnforcer()
    enforcer.register_protected_material(
        material_id="mat_1",
        title="Proprietary Whitepaper",
        holder="Acme Research",
        text_sample="Our confidential proprietary method increases tensor throughput by forty seven percent on all nodes.",
    )

    output = "The system achieved an increase in computing throughput through optimized memory layout."
    result = enforcer.evaluate_output(output)
    assert result.is_safe is True
    assert result.action == "allow"
    assert result.sanitized_output == output
    assert len(result.infringements) == 0


def test_source_attribution_enforcement():
    enforcer = ContentRightsEnforcer()

    output = "Quantum annealing relies on quantum fluctuations to find the global minimum of an objective function."
    sources = [
        {
            "title": "Quantum Annealing in Practice",
            "author": "Dr. Sarah Connor",
            "license": "CC-BY-4.0",
            "url": "https://example.org/qa-study",
        }
    ]

    result = enforcer.evaluate_output(output, sources=sources)
    assert result.action in ["attribute", "redact_and_attribute"]
    assert len(result.attributions_appended) == 1
    assert "Sources & Attribution:" in result.sanitized_output
    assert "**Quantum Annealing in Practice** by Dr. Sarah Connor (CC-BY-4.0) <https://example.org/qa-study>" in result.sanitized_output


def test_existing_attribution_not_duplicated():
    enforcer = ContentRightsEnforcer()

    output = "As shown in Quantum Annealing in Practice, quantum fluctuations help solve combinatorial tasks."
    sources = [
        {
            "title": "Quantum Annealing in Practice",
            "author": "Dr. Sarah Connor",
            "license": "CC-BY-4.0",
        }
    ]

    result = enforcer.evaluate_output(output, sources=sources)
    assert result.action == "allow"
    assert len(result.attributions_appended) == 0
    assert result.sanitized_output == output


def test_output_guard_integration_with_content_rights():
    # Register with singleton
    default_content_rights_enforcer.register_protected_material(
        material_id="lit_book_42",
        title="Galactic Guidebook",
        holder="Megadodo Publications",
        text_sample="Far out in the uncharted backwaters of the unfashionable end of the western spiral arm of the Galaxy lies a small unregarded yellow sun.",
    )

    guard = OutputGuard()
    gen_text = "It begins: Far out in the uncharted backwaters of the unfashionable end of the western spiral arm of the Galaxy lies a small unregarded yellow sun. That was where it all started."

    check_res = guard.evaluate(gen_text)
    assert check_res.action == "redact"
    assert check_res.threat_category == "copyright_infringement"
    assert "[REDACTED: Verbatim Copyrighted Material" in check_res.safe_content
    assert "western spiral arm" not in check_res.safe_content


def test_tagger_enforce_content_rights_bridge():
    from cognitive.knowledge.provenance.tagger import LicenseProvenanceTagger
    tagger = LicenseProvenanceTagger()

    output = "This explains the concept cleanly."
    sources = [
        {
            "title": "Clean Architecture Foundations",
            "author": "Robert Miller",
            "license": "MIT",
        }
    ]
    res = tagger.enforce_content_rights(output, sources=sources)
    assert "Sources & Attribution:" in res.sanitized_output
    assert "**Clean Architecture Foundations** by Robert Miller (MIT)" in res.sanitized_output
