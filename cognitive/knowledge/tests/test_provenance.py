"""Unit and integration tests for Copyright and License Provenance Tagger (Features 3.45, 3.46)."""

import pytest
from knowledge.provenance import (
    LicenseCategory,
    LicenseProvenanceTagger,
)


def test_spdx_permissive_license_tagging():
    tagger = LicenseProvenanceTagger()
    code_sample = """
    // SPDX-License-Identifier: Apache-2.0
    // Copyright (c) 2024 The Central-Intelligence Authors. All rights reserved.
    package main
    func main() {}
    """

    result = tagger.analyze(code_sample)

    assert result.spdx_identifier == "Apache-2.0"
    assert result.license_category == LicenseCategory.PERMISSIVE
    assert result.is_proprietary is False
    assert result.is_copyleft is False
    assert result.allows_commercial_use is True
    assert result.requires_source_disclosure is False
    assert len(result.copyright_notices) >= 1
    assert result.copyright_notices[0].year == 2024


def test_proprietary_confidential_content_flagging():
    tagger = LicenseProvenanceTagger()
    internal_doc = """
    CONFIDENTIAL AND PROPRIETARY — INTERNAL USE ONLY
    Copyright © 2025 Megacorp Inc.
    This document contains proprietary trade secret algorithms for algorithmic trading.
    Strictly prohibited from external release or model training.
    """

    result = tagger.analyze(internal_doc)

    assert result.is_proprietary is True
    assert result.license_category == LicenseCategory.PROPRIETARY
    assert result.allows_commercial_use is False
    assert any("proprietary_marker" in flag for flag in result.flags)
    assert any(c.holder and "Megacorp" in c.holder for c in result.copyright_notices)


def test_copyleft_gpl_detection_and_disclosure_flag():
    tagger = LicenseProvenanceTagger()
    gpl_code = """
    /*
     * This program is free software: you can redistribute it and/or modify
     * it under the terms of the GNU General Public License as published by
     * the Free Software Foundation, either version 3 of the License.
     */
    """

    result = tagger.analyze(gpl_code)

    assert result.is_copyleft is True
    assert result.license_category == LicenseCategory.COPYLEFT
    assert result.requires_source_disclosure is True
    assert any("copyleft" in flag for flag in result.flags)


def test_creative_commons_detection():
    tagger = LicenseProvenanceTagger()
    dataset_metadata = """
    Dataset published under Creative Commons CC-BY-NC 4.0 International license.
    Commercial redistribution prohibited.
    """

    result = tagger.analyze(dataset_metadata)

    assert result.license_category == LicenseCategory.CREATIVE_COMMONS
    assert result.allows_commercial_use is False  # NC flag restricts commercial use
    assert result.requires_attribution is True
