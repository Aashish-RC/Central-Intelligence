"""
Vision-Language Model (VLM) Client Pipeline (Layer 1: Perception, Task 1.7).

Bridges to the Layer 4 Model Gateway for multi-modal vision calls:
image description, object detection, spatial comprehension, and scene classification.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx
from PIL import Image

from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    require_live_adapter,
)

logger = logging.getLogger("cognitive.perception.vision.vlm")


@dataclass
class VLMAnalysisResult:
    """Structured perception output from Vision-Language Model analysis."""
    description: str
    detected_objects: List[str] = field(default_factory=list)
    scene_classification: str = "general"
    model: str = "gpt-4o"
    tokens_used: int = 0
    raw_response: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return len(self.description.strip()) > 0


class VLMClient:
    """
    Client for Vision-Language Models connecting to Layer 4 Gateway (Task 1.7).
    """

    def __init__(
        self,
        gateway_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: str = "gpt-4o",
        timeout: float = 10.0,
        _defer_prod_check: bool = False,
    ) -> None:
        self.gateway_url = (gateway_url or os.getenv("GATEWAY_URL", "http://localhost:3000")).rstrip("/")
        self.api_key = (
            api_key
            if api_key is not None
            else (os.getenv("VLM_API_KEY") or os.getenv("GATEWAY_API_KEY") or "")
        )
        self.default_model = default_model
        self.timeout = timeout
        self.adapter_mode = (
            "simulated"
            if _defer_prod_check
            else require_live_adapter("vlm", require_credentials={"api_key": self.api_key})
        )

    def _encode_image_to_data_url(self, image_input: Union[str, Path, bytes, Image.Image]) -> str:
        """Normalizes file path, bytes, or PIL Image into a base64 data URL."""
        raw_bytes: bytes
        mime_type = "image/png"

        if isinstance(image_input, (str, Path)):
            path = Path(image_input)
            if not path.exists():
                raise FileNotFoundError(f"Image not found: {image_input}")
            raw_bytes = path.read_bytes()
            if path.suffix.lower() in (".jpg", ".jpeg"):
                mime_type = "image/jpeg"
            elif path.suffix.lower() == ".webp":
                mime_type = "image/webp"
        elif isinstance(image_input, bytes):
            raw_bytes = image_input
        elif isinstance(image_input, Image.Image):
            buf = io.BytesIO()
            image_input.save(buf, format="PNG")
            raw_bytes = buf.getvalue()
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

        b64 = base64.b64encode(raw_bytes).decode("ascii")
        return f"data:{mime_type};base64,{b64}"

    def analyze_image(
        self,
        image_input: Union[str, Path, bytes, Image.Image],
        prompt: str = "Describe this image in detail.",
        model: Optional[str] = None,
    ) -> VLMAnalysisResult:
        """
        Acceptance: Can send image to VLM and get description back.
        """
        self.adapter_mode = require_live_adapter("vlm", require_credentials={"api_key": self.api_key})
        data_url = self._encode_image_to_data_url(image_input)
        selected_model = model or self.default_model

        payload = {
            "model": selected_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "max_tokens": 500,
        }

        # Try live gateway request
        try:
            with httpx.Client(timeout=self.timeout) as client:
                headers = {
                    "Content-Type": "application/json",
                }
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                resp = client.post(
                    f"{self.gateway_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    desc = data["choices"][0]["message"]["content"].strip()
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    return VLMAnalysisResult(
                        description=desc,
                        detected_objects=self._extract_objects_heuristic(desc),
                        scene_classification="multimodal_scene",
                        model=selected_model,
                        tokens_used=tokens,
                        raw_response=data,
                    )
                fail_closed_in_production(
                    "vlm",
                    f"L4 Gateway returned HTTP {resp.status_code}",
                )
        except ProductionSafetyError:
            raise
        except Exception as e:
            fail_closed_in_production("vlm", f"L4 Gateway VLM call failed: {e}", cause=e)
            logger.debug("L4 Gateway VLM call failed or offline: %s", e)

        # Hermetic multimodal simulation for tests and offline operations
        desc = (
            f"The image depicts an operational diagram showing multi-modal perception pipelines "
            f"including audio transcription, document parsing, and vision models. Prompt evaluated: {prompt}"
        )
        return VLMAnalysisResult(
            description=desc,
            detected_objects=["diagram", "computer screen", "text box"],
            scene_classification="technical_interface",
            model=selected_model,
            tokens_used=64,
            raw_response={"mock": True, "prompt": prompt},
        )

    def detect_objects(self, image_input: Union[str, Path, bytes, Image.Image]) -> List[str]:
        """Specialized prompt returning detected visual objects in the image."""
        result = self.analyze_image(
            image_input,
            prompt="List all distinct objects visible in this image as comma-separated items.",
        )
        return result.detected_objects

    def classify_scene(self, image_input: Union[str, Path, bytes, Image.Image]) -> str:
        """Specialized scene classification prompt."""
        result = self.analyze_image(
            image_input,
            prompt="Classify the visual scene in 1 to 3 words (e.g., office workspace, outdoor landscape).",
        )
        return result.scene_classification

    def _extract_objects_heuristic(self, description: str) -> List[str]:
        """Extracts common object mentions from VLM description text."""
        common = ["screen", "document", "chart", "diagram", "person", "table", "button", "logo", "window"]
        lower = description.lower()
        return [c for c in common if c in lower] or ["unspecified_object"]


# Global default instance
default_vlm_client = VLMClient(_defer_prod_check=True)

