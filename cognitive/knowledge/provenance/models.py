"""Data models for Copyright and License Provenance Tagging (Features 3.45, 3.46)."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LicenseCategory(str, Enum):
    PERMISSIVE = "permissive"
    COPYLEFT = "copyleft"
    PROPRIETARY = "proprietary"
    CREATIVE_COMMONS = "creative_commons"
    PUBLIC_DOMAIN = "public_domain"
    UNKNOWN = "unknown"


class CopyrightNotice(BaseModel):
    raw_notice: str
    holder: Optional[str] = None
    year: Optional[int] = None


class ProvenanceTagResult(BaseModel):
    license_id: str                      # e.g. "MIT", "Apache-2.0", "GPL-3.0", "PROPRIETARY"
    license_category: LicenseCategory
    is_proprietary: bool = False
    is_copyleft: bool = False
    allows_commercial_use: bool = True
    requires_attribution: bool = True
    requires_source_disclosure: bool = False
    copyright_notices: List[CopyrightNotice] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    spdx_identifier: Optional[str] = None
    flags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
