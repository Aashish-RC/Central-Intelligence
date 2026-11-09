"""Copyright and License Provenance Tagger (Features 3.45, 3.46)."""

import re
from typing import List, Optional
from knowledge.provenance.models import (
    CopyrightNotice,
    LicenseCategory,
    ProvenanceTagResult,
)


class LicenseProvenanceTagger:
    """Analyzes text/source headers to tag copyright provenance and license constraints."""

    SPDX_PATTERN = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9\.\-]+)", re.I)

    COPYRIGHT_PATTERNS = [
        re.compile(r"(?:copyright|©|\(c\))\s+(?:([0-9]{4})(?:-[0-9]{4})?)?\s*(?:by\s+)?([A-Za-z0-9\s,\.\-_]+?)(?:\.|\n|$|all rights)", re.I),
    ]

    PROPRIETARY_PATTERNS = [
        re.compile(r"\b(strictly confidential|proprietary and confidential|internal use only|trade secret|do not distribute|not for external release|confidential)\b", re.I),
    ]

    COPYLEFT_PATTERNS = [
        re.compile(r"\b(gnu general public license|gplv[23]|affero general public license|agplv3|copyleft)\b", re.I),
    ]

    PERMISSIVE_PATTERNS = [
        re.compile(r"\b(mit license|apache license|bsd [23]-clause|isc license|unlicense)\b", re.I),
    ]

    CREATIVE_COMMONS_PATTERNS = [
        re.compile(r"\b(creative commons|cc-by|cc-by-sa|cc-by-nc|cc-by-nd|cc0)\b", re.I),
    ]

    def analyze(self, text: str) -> ProvenanceTagResult:
        """Inspects text and extracts license identity, copyright notices, and usage flags."""
        flags: List[str] = []
        copyright_notices: List[CopyrightNotice] = []

        # 1. Check for SPDX License Identifier
        spdx_match = self.SPDX_PATTERN.search(text)
        spdx_id = spdx_match.group(1).strip() if spdx_match else None

        # 2. Extract Copyright Notices
        for pat in self.COPYRIGHT_PATTERNS:
            for match in pat.finditer(text):
                raw = match.group(0).strip()
                year_str = match.group(1)
                holder = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else None
                year = int(year_str) if year_str and year_str.isdigit() else None
                
                # Exclude noisy short matches
                if holder and len(holder) > 2 and not holder.lower().startswith("all rights"):
                    copyright_notices.append(
                        CopyrightNotice(raw_notice=raw, holder=holder, year=year)
                    )

        # 3. Check for Proprietary & Confidential markers
        is_proprietary = False
        for pat in self.PROPRIETARY_PATTERNS:
            match = pat.search(text)
            if match:
                is_proprietary = True
                flags.append(f"proprietary_marker: {match.group(1)}")

        # "All rights reserved" without an open source license is proprietary
        if not is_proprietary and not spdx_id and re.search(r"\ball rights reserved\b", text, re.I):
            has_oss = any(p.search(text) for p in self.PERMISSIVE_PATTERNS + self.COPYLEFT_PATTERNS + self.CREATIVE_COMMONS_PATTERNS)
            if not has_oss:
                is_proprietary = True
                flags.append("proprietary_marker: all rights reserved without open source license")

        # 4. Determine License Category and Rights
        if is_proprietary:
            return ProvenanceTagResult(
                license_id="PROPRIETARY",
                license_category=LicenseCategory.PROPRIETARY,
                is_proprietary=True,
                is_copyleft=False,
                allows_commercial_use=False,
                requires_attribution=True,
                requires_source_disclosure=False,
                copyright_notices=copyright_notices,
                confidence=0.95,
                spdx_identifier=spdx_id,
                flags=flags,
            )

        if spdx_id:
            return self._from_spdx(spdx_id, copyright_notices, flags)

        # 5. Check Copyleft
        for pat in self.COPYLEFT_PATTERNS:
            if pat.search(text):
                flags.append("reciprocal_copyleft_terms_detected")
                return ProvenanceTagResult(
                    license_id="GPL-Compatible",
                    license_category=LicenseCategory.COPYLEFT,
                    is_proprietary=False,
                    is_copyleft=True,
                    allows_commercial_use=True,
                    requires_attribution=True,
                    requires_source_disclosure=True,
                    copyright_notices=copyright_notices,
                    confidence=0.90,
                    flags=flags,
                )

        # 6. Check Creative Commons
        for pat in self.CREATIVE_COMMONS_PATTERNS:
            if pat.search(text):
                is_non_commercial = "nc" in text.lower()
                flags.append("creative_commons_license")
                return ProvenanceTagResult(
                    license_id="Creative-Commons",
                    license_category=LicenseCategory.CREATIVE_COMMONS,
                    is_proprietary=False,
                    is_copyleft=False,
                    allows_commercial_use=not is_non_commercial,
                    requires_attribution=True,
                    requires_source_disclosure=False,
                    copyright_notices=copyright_notices,
                    confidence=0.88,
                    flags=flags,
                )

        # 7. Check Permissive
        for pat in self.PERMISSIVE_PATTERNS:
            if pat.search(text):
                return ProvenanceTagResult(
                    license_id="Permissive-Open-Source",
                    license_category=LicenseCategory.PERMISSIVE,
                    is_proprietary=False,
                    is_copyleft=False,
                    allows_commercial_use=True,
                    requires_attribution=True,
                    requires_source_disclosure=False,
                    copyright_notices=copyright_notices,
                    confidence=0.90,
                    flags=flags,
                )

        # 8. Fallback Unknown
        return ProvenanceTagResult(
            license_id="UNKNOWN",
            license_category=LicenseCategory.UNKNOWN,
            is_proprietary=False,
            is_copyleft=False,
            allows_commercial_use=True,
            requires_attribution=len(copyright_notices) > 0,
            requires_source_disclosure=False,
            copyright_notices=copyright_notices,
            confidence=0.50,
            flags=["unspecified_license"],
        )

    def _from_spdx(self, spdx_id: str, notices: List[CopyrightNotice], flags: List[str]) -> ProvenanceTagResult:
        normalized = spdx_id.upper()

        if "MIT" in normalized or "APACHE" in normalized or "BSD" in normalized or "ISC" in normalized:
            return ProvenanceTagResult(
                license_id=spdx_id,
                license_category=LicenseCategory.PERMISSIVE,
                is_proprietary=False,
                is_copyleft=False,
                allows_commercial_use=True,
                requires_attribution=True,
                requires_source_disclosure=False,
                copyright_notices=notices,
                confidence=1.0,
                spdx_identifier=spdx_id,
                flags=flags,
            )

        if "GPL" in normalized or "AGPL" in normalized or "LGPL" in normalized or "MPL" in normalized:
            flags.append("copyleft_source_disclosure_required")
            return ProvenanceTagResult(
                license_id=spdx_id,
                license_category=LicenseCategory.COPYLEFT,
                is_proprietary=False,
                is_copyleft=True,
                allows_commercial_use=True,
                requires_attribution=True,
                requires_source_disclosure=True,
                copyright_notices=notices,
                confidence=1.0,
                spdx_identifier=spdx_id,
                flags=flags,
            )

        if "CC0" in normalized or "UNLICENSE" in normalized:
            return ProvenanceTagResult(
                license_id=spdx_id,
                license_category=LicenseCategory.PUBLIC_DOMAIN,
                is_proprietary=False,
                is_copyleft=False,
                allows_commercial_use=True,
                requires_attribution=False,
                requires_source_disclosure=False,
                copyright_notices=notices,
                confidence=1.0,
                spdx_identifier=spdx_id,
                flags=flags,
            )

        return ProvenanceTagResult(
            license_id=spdx_id,
            license_category=LicenseCategory.UNKNOWN,
            confidence=0.75,
            spdx_identifier=spdx_id,
            copyright_notices=notices,
            flags=flags,
        )
