"""Vision and OCR Perception modules (PaddleOCR, VLM client)."""

from cognitive.perception.vision.paddleocr_adapter import (
    ImageOCRResult,
    OCRTextBox,
    PaddleOCRAdapter,
    default_paddleocr_adapter,
)

__all__ = [
    "ImageOCRResult",
    "OCRTextBox",
    "PaddleOCRAdapter",
    "default_paddleocr_adapter",
]

