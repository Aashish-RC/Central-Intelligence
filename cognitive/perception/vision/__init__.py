"""Vision and OCR Perception modules (PaddleOCR, VLM client)."""

from cognitive.perception.vision.paddleocr_adapter import (
    ImageOCRResult,
    OCRTextBox,
    PaddleOCRAdapter,
    default_paddleocr_adapter,
)
from cognitive.perception.vision.vlm_client import (
    VLMAnalysisResult,
    VLMClient,
    default_vlm_client,
)

__all__ = [
    "ImageOCRResult",
    "OCRTextBox",
    "PaddleOCRAdapter",
    "default_paddleocr_adapter",
    "VLMAnalysisResult",
    "VLMClient",
    "default_vlm_client",
]
