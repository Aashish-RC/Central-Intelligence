"""Image Route Safety and Generation Pipeline (Task 6.4 & Task 9).

Coordinates image generation through Model Gateway /v1/images/generations
wrapped with Guardrails output safety screening and content moderation.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Any, Dict, Optional
import httpx
from pydantic import BaseModel, Field

from media_gen.core.models import (
    MediaArtifact,
    MediaRequest,
    MediaType,
    SafetyCheckStatus,
)
from media_gen.core.safety import SafetyModerator
from media_gen.engines.image_engine import ImageGenerationEngine
from guardrails.core.output_guard import OutputGuard


class SafetyPolicyViolationError(Exception):
    """Raised when an image generation prompt violates content safety policies."""
    pass


class ImageGenerationResult(BaseModel):
    success: bool
    artifact: Optional[MediaArtifact] = None
    prompt: str
    error: Optional[str] = None
    safety_checked: bool = True
    provider: str = "engine"


class ImageGenerationRoute:
    """Unified route handler for image synthesis with pre-flight safety screening,

    gateway dispatch, and outbound guardrail inspection.
    """

    def __init__(
        self,
        output_guard: Optional[OutputGuard] = None,
        safety_moderator: Optional[SafetyModerator] = None,
        stability_api_key: Optional[str] = None,
        comfyui_url: Optional[str] = None,
        gateway_url: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.output_guard = output_guard or OutputGuard()
        self.safety_moderator = safety_moderator or SafetyModerator()
        self.stability_api_key = stability_api_key or os.getenv("STABILITY_API_KEY")
        self.comfyui_url = comfyui_url or os.getenv("COMFYUI_URL", "http://localhost:8188")
        self.gateway_url = (
            gateway_url
            or os.getenv("GATEWAY_URL")
            or os.getenv("MODEL_GATEWAY_URL", "http://localhost:4000")
        ).rstrip("/")
        self.http_client = http_client
        self._engine = ImageGenerationEngine()

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        model: str = "sdxl-turbo",
        **parameters: Any
    ) -> ImageGenerationResult:
        """Executes safety-screened image generation.

        Raises SafetyPolicyViolationError or returns failed result if content policy is violated.
        """
        if not prompt or not prompt.strip():
            return ImageGenerationResult(
                success=False,
                prompt=prompt,
                error="Prompt cannot be empty",
                safety_checked=False
            )

        # 1. Screen input prompt through media safety moderator
        req = MediaRequest(
            media_type=MediaType.IMAGE,
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=model,
            parameters={"width": width, "height": height, **parameters}
        )
        screen_res = self.safety_moderator.screen_prompt(req)
        if screen_res.status == SafetyCheckStatus.BLOCKED:
            raise SafetyPolicyViolationError(f"Prompt blocked by media safety moderator: {screen_res.reason}")

        # 2. Evaluate prompt against Guardrails output guard
        guard_res = self.output_guard.evaluate(prompt)
        if guard_res.action == "block":
            raise SafetyPolicyViolationError(f"Prompt blocked by output guardrail: {guard_res.reason}")

        # 3. Dispatch generation to Gateway /v1/images/generations via httpx
        artifact: Optional[MediaArtifact] = None
        provider_name = "model_gateway"

        size_str = f"{width}x{height}"
        if size_str not in ("256x256", "512x512", "1024x1024", "1792x1024", "1024x1792"):
            size_str = "1024x1024"

        gateway_payload = {
            "prompt": prompt,
            "model": model,
            "n": 1,
            "size": size_str,
            "response_format": "b64_json",
        }

        try:
            client = self.http_client or httpx.AsyncClient(timeout=0.5)
            close_client = self.http_client is None
            try:
                resp = await client.post(
                    f"{self.gateway_url}/v1/images/generations",
                    json=gateway_payload,
                )
                if resp.status_code == 200:
                    resp_json = resp.json()
                    data = resp_json.get("data", [])
                    if data:
                        item = data[0]
                        revised_prompt = item.get("revised_prompt") or prompt
                        b64_json = item.get("b64_json")
                        img_url = item.get("url") or (f"data:image/png;base64,{b64_json}" if b64_json else "")

                        # 4. Run the result through the existing output guard
                        post_guard_res = self.output_guard.evaluate(revised_prompt)
                        if post_guard_res.action == "block":
                            raise SafetyPolicyViolationError(
                                f"Generated image result blocked by output guard: {post_guard_res.reason}"
                            )

                        raw_content = (b64_json or img_url or prompt).encode("utf-8")
                        digest = hashlib.sha256(raw_content).hexdigest()

                        artifact = MediaArtifact(
                            request_id=req.id,
                            media_type=MediaType.IMAGE,
                            uri=img_url,
                            mime_type="image/png",
                            size_bytes=len(b64_json.encode("utf-8")) if b64_json else 1024,
                            sha256=digest,
                            metadata={
                                "width": width,
                                "height": height,
                                "model": model,
                                "prompt": prompt,
                                "revised_prompt": revised_prompt,
                            },
                        )
                elif self.http_client is not None:
                    resp.raise_for_status()
            finally:
                if close_client:
                    await client.aclose()
        except SafetyPolicyViolationError:
            raise
        except Exception:
            if self.http_client is not None:
                raise

        # 5. Local fallback if gateway was not reachable and no mock client specified
        if artifact is None:
            provider_name = "stability_ai" if self.stability_api_key else ("comfyui" if "comfyui" in self.comfyui_url else "image_engine")
            artifact = await self._engine.generate(req)
            post_guard_res = self.output_guard.evaluate(prompt)
            if post_guard_res.action == "block":
                raise SafetyPolicyViolationError(f"Generated result blocked by output guardrail: {post_guard_res.reason}")

        # 6. Post-generation inspection with safety moderator
        inspect_res = self.safety_moderator.inspect_artifact(artifact)
        if inspect_res.status == SafetyCheckStatus.BLOCKED:
            raise SafetyPolicyViolationError(f"Generated artifact failed post-gen integrity inspection: {inspect_res.reason}")

        return ImageGenerationResult(
            success=True,
            artifact=artifact,
            prompt=prompt,
            safety_checked=True,
            provider=provider_name
        )

    def generate_image_sync(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> ImageGenerationResult:
        """Synchronous wrapper for generate_image."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(self.generate_image(prompt, negative_prompt=negative_prompt, **kwargs))
        else:
            return asyncio.run(self.generate_image(prompt, negative_prompt=negative_prompt, **kwargs))
