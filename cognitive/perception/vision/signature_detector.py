"""Signature and Stamp Detection for Contracts & Scanned Forms (L1 Feature 1.19)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Union

from PIL import Image

from cognitive.perception.vision.paddleocr_adapter import PaddleOCRAdapter


@dataclass
class DetectedMark:
    """Detected signature or official stamp region on a page."""

    kind: str  # "signature" or "stamp"
    page_number: int
    bbox: Tuple[int, int, int, int]
    confidence: float
    label: str = ""


@dataclass
class SignatureDetectionResult:
    """Summary of signatures and stamps detected in a document or image."""

    has_signature: bool
    has_stamp: bool
    marks: List[DetectedMark] = field(default_factory=list)


_SIGNATURE_KEYWORDS = re.compile(r"\b(signature|signed by|authorized signatory|x_+)\b", re.I)
_STAMP_KEYWORDS = re.compile(r"\b(approved|notary|confidential|official seal|stamp)\b", re.I)


class SignatureDetector:
    """Detects handwritten signatures and ink stamps in PDFs and images."""

    def __init__(self, ocr_adapter: Optional[PaddleOCRAdapter] = None) -> None:
        self.ocr_adapter = ocr_adapter or PaddleOCRAdapter()

    def detect_in_image(
        self,
        image_input: Union[str, Path, Image.Image],
        page_number: int = 1,
    ) -> SignatureDetectionResult:
        marks: List[DetectedMark] = []
        img = Image.open(image_input) if isinstance(image_input, (str, Path)) else image_input

        # 1. Textual anchor cues near signature/stamp boxes
        ocr_res = self.ocr_adapter.extract_text_from_image(img)
        for box in ocr_res.text_boxes:
            if _SIGNATURE_KEYWORDS.search(box.text):
                b = box.box[0] if box.box else [0, 0]
                marks.append(
                    DetectedMark(
                        kind="signature",
                        page_number=page_number,
                        bbox=(int(b[0]), int(b[1]), int(b[0]) + 180, int(b[1]) + 45),
                        confidence=0.88,
                        label=box.text,
                    )
                )
            elif _STAMP_KEYWORDS.search(box.text):
                b = box.box[0] if box.box else [0, 0]
                marks.append(
                    DetectedMark(
                        kind="stamp",
                        page_number=page_number,
                        bbox=(int(b[0]), int(b[1]), int(b[0]) + 110, int(b[1]) + 110),
                        confidence=0.84,
                        label=box.text,
                    )
                )

        # 2. Ink-density / stroke heuristic in lower half (handles blank/scanned signature strokes)
        gray = img.convert("L")
        w, h = gray.size
        if w > 0 and h > 0:
            lower = gray.crop((0, h // 2, w, h))
            pixels = list(lower.getdata())
            dark = [i for i, p in enumerate(pixels) if p < 120]
            ratio = len(dark) / max(1, len(pixels))
            if 0.003 <= ratio <= 0.35 and not any(m.kind == "signature" for m in marks):
                marks.append(
                    DetectedMark(
                        kind="signature",
                        page_number=page_number,
                        bbox=(w // 8, (h * 5) // 8, (w * 5) // 8, (h * 7) // 8),
                        confidence=0.76,
                        label="ink_stroke_region",
                    )
                )

        return SignatureDetectionResult(
            has_signature=any(m.kind == "signature" for m in marks),
            has_stamp=any(m.kind == "stamp" for m in marks),
            marks=marks,
        )

    def detect_in_pdf(self, pdf_path: str | Path) -> SignatureDetectionResult:
        raw = Path(pdf_path).read_bytes().decode("latin-1", errors="ignore")
        marks: List[DetectedMark] = []
        if _SIGNATURE_KEYWORDS.search(raw) or "/Sig" in raw:
            marks.append(
                DetectedMark(
                    kind="signature",
                    page_number=1,
                    bbox=(72, 120, 280, 170),
                    confidence=0.91,
                    label="pdf_signature_field",
                )
            )
        if _STAMP_KEYWORDS.search(raw) or "/Stamp" in raw:
            marks.append(
                DetectedMark(
                    kind="stamp",
                    page_number=1,
                    bbox=(320, 120, 420, 220),
                    confidence=0.87,
                    label="pdf_stamp_annotation",
                )
            )
        return SignatureDetectionResult(
            has_signature=any(m.kind == "signature" for m in marks),
            has_stamp=any(m.kind == "stamp" for m in marks),
            marks=marks,
        )

