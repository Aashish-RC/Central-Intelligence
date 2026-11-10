"""
Consent management package.
"""

from .c15t_adapter import (
    C15tConsentAdapter,
    ConsentPurpose,
    ConsentRecord,
    get_default_consent_adapter,
    set_default_consent_adapter,
)

__all__ = [
    "C15tConsentAdapter",
    "ConsentPurpose",
    "ConsentRecord",
    "get_default_consent_adapter",
    "set_default_consent_adapter",
]

