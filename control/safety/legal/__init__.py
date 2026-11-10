"""
Legal safety package.
"""

from .authority_request import (
    AuthorityRequestHandler,
    AuthorityRequestRecord,
    RequestType,
    default_authority_handler,
)
from .legal_hold import (
    LegalHoldManager,
    LegalHoldRecord,
    LegalHoldStatus,
    default_legal_hold_manager,
)

__all__ = [
    "AuthorityRequestHandler",
    "AuthorityRequestRecord",
    "RequestType",
    "default_authority_handler",
    "LegalHoldManager",
    "LegalHoldRecord",
    "LegalHoldStatus",
    "default_legal_hold_manager",
]
