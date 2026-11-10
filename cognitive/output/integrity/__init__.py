"""Output integrity, watermarking, and surgical claim diff patching."""

from cognitive.output.integrity.claim_diff_patcher import (
    ClaimDiffPatcher,
    RefutedClaim,
    ClaimPatchResult,
)
from cognitive.output.integrity.watermarker import (
    CryptographicWatermarker,
    WatermarkPayload,
    ProvenanceVerificationResult,
)

__all__ = [
    "ClaimDiffPatcher",
    "RefutedClaim",
    "ClaimPatchResult",
    "CryptographicWatermarker",
    "WatermarkPayload",
    "ProvenanceVerificationResult",
]
