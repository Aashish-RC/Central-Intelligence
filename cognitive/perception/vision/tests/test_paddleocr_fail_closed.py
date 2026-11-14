"""Regression tests verifying PaddleOCR fails closed in live mode without silent mock fallback."""

import os
import pytest
from PIL import Image

from control.safety.production_guard import ProductionSafetyError
import cognitive.perception.vision.paddleocr_adapter as ocr_module
from cognitive.perception.vision.paddleocr_adapter import (
    PaddleOCRAdapter,
    ImageOCRResult,
)


def test_live_mode_without_paddleocr_fails_closed(monkeypatch):
    """When _PADDLEOCR_AVAILABLE is False in live mode, extract_text_from_image raises ProductionSafetyError."""
    monkeypatch.setattr(ocr_module, "_PADDLEOCR_AVAILABLE", False)
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    adapter = PaddleOCRAdapter(_defer_prod_check=True)
    adapter.adapter_mode = "live"
    img = Image.new("RGB", (100, 100), color="white")

    with pytest.raises(ProductionSafetyError) as exc_info:
        adapter.extract_text_from_image(img)

    assert "PaddleOCR engine is unavailable" in str(exc_info.value)


def test_simulated_mode_returns_marker_text(monkeypatch):
    """When in simulated mode with CI_TEST_MODE=1, extract_text_from_image returns fallback text."""
    monkeypatch.setenv("ADAPTER_MODE", "simulated")
    monkeypatch.setenv("CI_TEST_MODE", "1")

    adapter = PaddleOCRAdapter(_defer_prod_check=True)
    adapter.adapter_mode = "simulated"
    img = Image.new("RGB", (100, 100), color="white")

    result = adapter.extract_text_from_image(img)
    assert isinstance(result, ImageOCRResult)
    assert "Central Intelligence System Authorization Badge 2026" in result.full_text


@pytest.mark.live
@pytest.mark.skipif(os.getenv("PADDLEOCR_LIVE") != "1", reason="Requires PADDLEOCR_LIVE=1")
def test_live_mode_with_engine_calls_real_ocr():
    """Live test running real PaddleOCR extraction against a test image."""
    adapter = PaddleOCRAdapter()
    img = Image.new("RGB", (200, 50), color="white")
    result = adapter.extract_text_from_image(img)
    assert isinstance(result, ImageOCRResult)
    assert result.full_text != "Central Intelligence System Authorization Badge 2026"

