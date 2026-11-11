"""Image-to-Image Transformation Engine (L6 Feature 6.08)."""

from __future__ import annotations

from typing import Optional, Tuple

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from cognitive.output.media_gen.engines._pil_helpers import (
    BaseMediaEngine,
    MediaArtifact,
    MediaRequest,
    MediaType,
    build_artifact,
    encode_png,
    load_image_input,
)


class ImageToImageEngine(BaseMediaEngine):
    """Transforms an input image according to strength, prompt mood, and enhancement controls."""

    def supported_type(self) -> MediaType:
        return MediaType.IMAGE

    def transform_image(
        self,
        source: Image.Image | bytes | str,
        prompt: str,
        strength: float = 0.65,
        tint: Optional[Tuple[int, int, int]] = None,
    ) -> Image.Image:
        img = load_image_input(source)
        strength = max(0.0, min(1.0, strength))
        stylized = img.filter(ImageFilter.SMOOTH_MORE)
        stylized = ImageEnhance.Color(stylized).enhance(1.0 + 0.5 * strength)
        stylized = ImageEnhance.Contrast(stylized).enhance(1.0 + 0.3 * strength)

        if tint is not None or any(w in prompt.lower() for w in ("warm", "sunset", "cyber", "styliz")):
            target_tint = tint or ((220, 120, 60) if "warm" in prompt.lower() or "sunset" in prompt.lower() else (80, 160, 230))
            tinted = ImageOps.colorize(ImageOps.grayscale(stylized), black=(18, 18, 32), white=target_tint)
            stylized = Image.blend(stylized, tinted, alpha=strength * 0.55)

        return Image.blend(img, stylized, alpha=strength)

    async def generate(self, request: MediaRequest) -> MediaArtifact:
        if request.media_type != MediaType.IMAGE:
            raise ValueError(f"ImageToImageEngine cannot handle {request.media_type}")
        src = request.parameters.get("source_image")
        strength = float(request.parameters.get("strength", 0.65))
        out_img = self.transform_image(src, prompt=request.prompt, strength=strength)
        raw_bytes = encode_png(out_img)
        return build_artifact(
            request,
            raw_bytes,
            {
                "engine": "image_to_image",
                "width": out_img.width,
                "height": out_img.height,
                "strength": strength,
                "prompt": request.prompt,
            },
        )

