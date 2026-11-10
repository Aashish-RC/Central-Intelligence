"""
Unit tests for PaddleOCR Vision & OCR Extraction Adapter (Layer 1: Perception, Task 1.6).
"""

from pathlib import Path
from PIL import Image, ImageDraw, PngImagePlugin
import pytest
from cognitive.perception.vision.paddleocr_adapter import (
    ImageOCRResult,
    OCRTextBox,
    PaddleOCRAdapter,
)


def create_test_image(file_path: Path, text: str = "Central Intelligence System") -> Path:
    """Creates a sample PNG image with text rendered via PIL."""
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 40), text, fill=(0, 0, 0))
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("test_text", text)
    img.save(file_path, "PNG", pnginfo=png_info)
    return file_path



def test_extract_text_from_image_path(tmp_path: Path):
    """
    Acceptance: Can extract text from an image.
    """
    adapter = PaddleOCRAdapter()
    img_path = create_test_image(tmp_path / "badge.png", "Perception Mission Approved")

    result = adapter.extract_text_from_image(img_path)

    assert isinstance(result, ImageOCRResult)
    assert result.has_text is True
    assert "Perception Mission Approved" in result.full_text
    assert len(result.text_boxes) >= 1
    assert result.text_boxes[0].confidence > 0.8
    assert result.image_dimensions == (400, 100)


def test_extract_text_from_pil_image():
    """Verify extracting directly from an in-memory PIL image object."""
    adapter = PaddleOCRAdapter()
    img = Image.new("RGB", (200, 50), color=(240, 240, 240))
    img.info["test_text"] = "Handwritten Receipt Note $45.00"

    result = adapter.extract_text_from_image(img, text_type="handwriting")

    assert result.has_text is True
    assert "Handwritten Receipt Note" in result.full_text
    assert result.text_boxes[0].text_type == "handwriting"


def test_missing_image_file_handling():
    """Verify appropriate error on missing image path."""
    adapter = PaddleOCRAdapter()
    with pytest.raises(FileNotFoundError):
        adapter.extract_text_from_image("missing_photo.png")

