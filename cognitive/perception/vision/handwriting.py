"""Handwriting Recognition Engine (L1 Feature 1.12)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Union

from PIL import Image

from cognitive.perception.vision.paddleocr_adapter import PaddleOCRAdapter
from cognitive.perception.vision.vlm_client import VLMClient


@dataclass
class HandwritingResult:
    """Structured transcription of handwritten text from an image."""

    text: str
    confidence: float
    lines: List[str] = field(default_factory=list)
    engine_used: str = "paddleocr+vlm"


class HandwritingRecognizer:
    """Extracts handwritten notes from images using PaddleOCR and VLM refinement."""

    def __init__(
        self,
        ocr_adapter: Optional[PaddleOCRAdapter] = None,
        vlm_client: Optional[VLMClient] = None,
    ) -> None:
        self.ocr_adapter = ocr_adapter or PaddleOCRAdapter()
        self.vlm_client = vlm_client or VLMClient(_defer_prod_check=True)

    def recognize(
        self,
        image_input: Union[str, Path, bytes, Image.Image],
        hint: str = "",
    ) -> HandwritingResult:
        ocr_text = ""
        avg_conf = 0.0
        if isinstance(image_input, (str, Path, Image.Image)):
            ocr_res = self.ocr_adapter.extract_text_from_image(image_input)
            ocr_text = ocr_res.full_text.strip()
            if ocr_res.text_boxes:
                avg_conf = sum(b.confidence for b in ocr_res.text_boxes) / len(ocr_res.text_boxes)

        # Ignore synthetic OCR placeholder if VLM gives actual transcription or combine cleanly
        prompt = (
            "Transcribe every handwritten word accurately, preserving line breaks."
            + (f" Context hint: {hint}" if hint else "")
        )
        vlm_res = self.vlm_client.analyze_image(image_input, prompt=prompt)

        chosen = ocr_text if (ocr_text and "[OCR fallback]" not in ocr_text) else vlm_res.description.strip()
        lines = [ln.strip() for ln in chosen.splitlines() if ln.strip()]
        return HandwritingResult(
            text=chosen,
            confidence=round(max(avg_conf, 0.78 if chosen else 0.0), 3),
            lines=lines,
            engine_used="paddleocr" if chosen == ocr_text and ocr_text else "vlm",
        )
