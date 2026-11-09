"""Copyright & License Provenance Tagging package (Features 3.45, 3.46)."""

from knowledge.provenance.models import (
    CopyrightNotice,
    LicenseCategory,
    ProvenanceTagResult,
)
from knowledge.provenance.tagger import LicenseProvenanceTagger

__all__ = [
    "CopyrightNotice",
    "LicenseCategory",
    "ProvenanceTagResult",
    "LicenseProvenanceTagger",
]
