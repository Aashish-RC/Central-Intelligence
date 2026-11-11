"""Visual Question Answering (VQA) Bridge between VLM & L4 Reasoning (L1 Feature 1.41)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image

from cognitive.perception.vision.paddleocr_adapter import PaddleOCRAdapter
from cognitive.perception.vision.vlm_client import VLMAnalysisResult, VLMClient


@dataclass
class VQAResponse:
    """Structured VQA answer combining VLM visual reasoning and OCR text grounding."""

    question: str
    answer: str
    confidence: float
    detected_objects: List[str] = field(default_factory=list)
    extracted_text: str = ""
    scene: str = "general"
    model: str = "gpt-4o"
    metadata: Dict[str, Any] = field(default_factory=dict)


class VisualQuestionAnsweringEngine:
    """Answers structured questions over images and scanned documents."""

    def __init__(
        self,
        vlm_client: Optional[VLMClient] = None,
        ocr_adapter: Optional[PaddleOCRAdapter] = None,
    ) -> None:
        self.vlm_client = vlm_client or VLMClient(_defer_prod_check=True)
        self.ocr_adapter = ocr_adapter or PaddleOCRAdapter()

    def answer_question(
        self,
        image_input: Union[str, Path, bytes, Image.Image],
        question: str,
        include_ocr: bool = True,
    ) -> VQAResponse:
        if not question.strip():
            raise ValueError("question must not be empty")

        ocr_text = ""
        if include_ocr and isinstance(image_input, (str, Path, Image.Image)):
            ocr_res = self.ocr_adapter.extract_text_from_image(image_input)
            ocr_text = ocr_res.full_text.strip()

        prompt = (
            f"Question: {question.strip()}\n"
            + (f"Visible OCR text: {ocr_text}\n" if ocr_text else "")
            + "Provide a concise, grounded answer."
        )
        vlm_res: VLMAnalysisResult = self.vlm_client.analyze_image(image_input, prompt=prompt)
        confidence = 0.9 if vlm_res.is_success and ocr_text else (0.8 if vlm_res.is_success else 0.3)

        return VQAResponse(
            question=question.strip(),
            answer=vlm_res.description,
            confidence=confidence,
            detected_objects=list(vlm_res.detected_objects),
            extracted_text=ocr_text,
            scene=vlm_res.scene_classification,
            model=vlm_res.model,
            metadata={"tokens_used": vlm_res.tokens_used, "has_ocr_grounding": bool(ocr_text)},
        )

