"""
Abuse prevention and detector package (Features 10.48, 10.49, 10.50).
"""

from .multi_account_detector import (
    MultiAccountAssessment,
    MultiAccountDetector,
    default_multi_account_detector,
)
from .quota_gaming_detector import (
    QuotaGamingAssessment,
    QuotaGamingDetector,
    default_quota_gaming_detector,
)
from .automated_misuse_detector import (
    AutomatedMisuseAssessment,
    AutomatedMisuseDetector,
    default_automated_misuse_detector,
)

__all__ = [
    "MultiAccountAssessment",
    "MultiAccountDetector",
    "default_multi_account_detector",
    "QuotaGamingAssessment",
    "QuotaGamingDetector",
    "default_quota_gaming_detector",
    "AutomatedMisuseAssessment",
    "AutomatedMisuseDetector",
    "default_automated_misuse_detector",
]
