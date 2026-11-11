"""Mathematical Formula Recognition -> LaTeX Output (L1 Feature 1.17)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from PIL import Image

from cognitive.perception.vision.vlm_client import VLMClient


@dataclass
class FormulaResult:
    """Recognized mathematical formula rendered in LaTeX."""

    latex: str
    confidence: float
    backend: str


class FormulaRecognizer:
    """Converts images containing equations into normalized LaTeX strings."""

    def __init__(self, vlm_client: Optional[VLMClient] = None) -> None:
        self.vlm_client = vlm_client or VLMClient(_defer_prod_check=True)

    @staticmethod
    def _clean_latex(raw: str) -> str:
        text = raw.strip()
        for fence in ("```latex", "```tex", "```", "$$", "$"):
            if text.startswith(fence):
                text = text[len(fence) :]
            if text.endswith(fence):
                text = text[: -len(fence)]
        return text.strip()

    def recognize(self, image_input: Union[str, Path, bytes, Image.Image]) -> FormulaResult:
        res = self.vlm_client.analyze_image(
            image_input,
            prompt="Transcribe the mathematical equation strictly as valid LaTeX without commentary.",
        )
        latex = self._clean_latex(res.description)
        return FormulaResult(
            latex=latex,
            confidence=0.88 if res.is_success and latex else 0.0,
            backend=f"vlm:{res.model}",
        )

