"""Tests for VQA (1.41), Handwriting (1.12), and Signature Detection (1.19)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image, ImageDraw

from cognitive.perception.vision.handwriting import HandwritingRecognizer
from cognitive.perception.vision.paddleocr_adapter import ImageOCRResult, OCRTextBox
from cognitive.perception.vision.signature_detector import SignatureDetector
from cognitive.perception.vision.vlm_client import VLMAnalysisResult, VLMClient
from cognitive.perception.vision.vqa import VisualQuestionAnsweringEngine


def test_vqa_and_handwriting_and_signature(tmp_path: Path) -> None:
    img = Image.new("RGB", (200, 120), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.line([(20, 85), (150, 95), (180, 80)], fill=(10, 10, 10), width=4)

    mock_vlm = MagicMock(spec=VLMClient)
    mock_vlm.analyze_image.return_value = VLMAnalysisResult(
        description="A signed whiteboard note reading Meeting at 3 PM",
        detected_objects=["note"],
        scene_classification="document",
    )
    mock_ocr = MagicMock()
    mock_ocr.extract_text_from_image.return_value = ImageOCRResult(
        text_boxes=[OCRTextBox(text="Meeting at 3 PM", confidence=0.95, box=[[10, 10]])],
        full_text="Meeting at 3 PM",
    )

    vqa = VisualQuestionAnsweringEngine(vlm_client=mock_vlm, ocr_adapter=mock_ocr)
    ans = vqa.answer_question(img, "What's in this image?")
    assert "Meeting at 3 PM" in ans.answer
    assert ans.confidence >= 0.8

    hw = HandwritingRecognizer(ocr_adapter=mock_ocr, vlm_client=mock_vlm)
    hw_res = hw.recognize(img)
    assert hw_res.text == "Meeting at 3 PM"

    sig_ocr = MagicMock()
    sig_ocr.extract_text_from_image.return_value = ImageOCRResult(
        text_boxes=[OCRTextBox(text="Authorized Signature: ________", confidence=0.92, box=[[15, 70]])],
        full_text="Authorized Signature: ________",
    )
    detector = SignatureDetector(ocr_adapter=sig_ocr)
    sig_res = detector.detect_in_image(img)
    assert sig_res.has_signature is True

    contract_pdf = tmp_path / "contract.pdf"
    contract_pdf.write_bytes(b"%PDF-1.4\n/Type /Sig\n(Signature: John Doe) Tj\n%%EOF")
    pdf_res = detector.detect_in_pdf(contract_pdf)
    assert pdf_res.has_signature is True

