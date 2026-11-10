"""Unit tests for Citation Formatter (Feature 6.33)."""

import pytest
from cognitive.output.citations.formatter import (
    CitationFormatter,
    CitationSource,
    CitationStyle,
)
from cognitive.knowledge.provenance.models import (
    ProvenanceTagResult,
    LicenseCategory,
    CopyrightNotice,
)


def test_can_format_citations_in_apa_and_mla():
    formatter = CitationFormatter()

    source = CitationSource(
        title="Attention Is All You Need",
        authors=["Vaswani, Ashish", "Shazeer, Noam"],
        year=2017,
        publication="Advances in Neural Information Processing Systems",
        volume="30",
        pages="5998-6008",
        url="https://arxiv.org/abs/1706.03762",
    )

    # Format APA
    apa_result = formatter.format(source, CitationStyle.APA)
    assert "Vaswani, Ashish, & Shazeer, Noam." in apa_result
    assert "(2017)." in apa_result
    assert "Attention Is All You Need." in apa_result
    assert "*Advances in Neural Information Processing Systems*" in apa_result
    assert "https://arxiv.org/abs/1706.03762" in apa_result

    # Format MLA
    mla_result = formatter.format(source, CitationStyle.MLA)
    assert "Vaswani, Ashish, and Shazeer, Noam." in mla_result
    assert '"Attention Is All You Need."' in mla_result
    assert "*Advances in Neural Information Processing Systems*" in mla_result
    assert "pp. 5998-6008" in mla_result


def test_inline_and_footnote_formatting():
    formatter = CitationFormatter()
    source = CitationSource(
        title="Deep Residual Learning for Image Recognition",
        authors=["He, Kaiming", "Zhang, Xiangyu", "Ren, Shaoqing", "Sun, Jian"],
        year=2016,
    )

    inline = formatter.format(source, CitationStyle.INLINE)
    assert inline == "(He et al., 2016)"


def test_wires_l3_knowledge_provenance():
    formatter = CitationFormatter()

    provenance = ProvenanceTagResult(
        license_id="Apache-2.0",
        license_category=LicenseCategory.PERMISSIVE,
        copyright_notices=[
            CopyrightNotice(raw_notice="Copyright 2026 DeepMind", holder="Google DeepMind", year=2026)
        ],
    )

    citation = formatter.format_from_provenance(
        provenance=provenance,
        title="Central Intelligence Neural Router",
        style=CitationStyle.APA,
        url="https://github.com/Aashish-RC/Central-Intelligence",
    )

    assert "Google DeepMind." in citation
    assert "(2026)." in citation
    assert "Central Intelligence Neural Router." in citation
    assert "License: Apache-2.0" in citation

