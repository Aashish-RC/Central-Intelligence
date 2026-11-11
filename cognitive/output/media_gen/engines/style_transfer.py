"""Artistic Style Transfer Engine (L6 Feature 6.12)."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

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


_STYLE_PRESETS: Dict[str, Tuple[Tuple[int, int, int], Tuple[int, int, int], float]] = {
    "van_gogh": ((16, 32, 82), (242, 198, 65), 1.6),
    "monet": ((36, 62, 88), (218, 226, 236), 1.25),
    "cyberpunk": ((18, 8, 42), (0, 235, 255), 1.8),
    "watercolor": ((42, 48, 56), (245, 238, 224), 1.15),
}


class StyleTransferEngine(BaseMediaEngine):
    """Applies named artistic styles or reference-image palette tone transfer."""

    def supported_type(self) -> MediaType:
        return MediaType.IMAGE

    def apply_style(
        self,
        content_image: Image.Image | bytes | str,
        style_name: str = "van_gogh",
        style_reference: Optional[Image.Image | bytes | str] = None,
        intensity: float = 0.75,
    ) -> Image.Image:
        img = load_image_input(content_image)
        intensity = max(0.0, min(1.0, intensity))

        # Painterly stroke smoothing + edge accentuation
        painterly = img.filter(ImageFilter.ModeFilter(size=3)) if min(img.size) >= 16 else img.copy()

        if style_reference is not None:
            ref = load_image_input(style_reference).resize((32, 32))
            pixels = list(ref.getdata())
            r_avg = sum(p[0] for p in pixels) // len(pixels)
            g_avg = sum(p[1] for p in pixels) // len(pixels)
            b_avg = sum(p[2] for p in pixels) // len(pixels)
            black_t = (max(0, r_avg // 4), max(0, g_avg // 4), max(0, b_avg // 4))
            white_t = (min(255, r_avg + 60), min(255, g_avg + 60), min(255, b_avg + 60))
            contrast_boost = 1.4
        else:
            key = style_name.lower().replace(" ", "_").replace("-", "_")
            black_t, white_t, contrast_boost = _STYLE_PRESETS.get(key, _STYLE_PRESETS["van_gogh"])

        duotone = ImageOps.colorize(ImageOps.grayscale(painterly), black=black_t, white=white_t)
        blended = Image.blend(painterly, duotone, alpha=intensity)
        return ImageEnhance.Contrast(blended).enhance(contrast_boost)

    async def generate(self, request: MediaRequest) -> MediaArtifact:
        if request.media_type != MediaType.IMAGE:
            raise ValueError(f"StyleTransferEngine cannot handle {request.media_type}")
        src = request.parameters.get("source_image")
        style_name = str(request.parameters.get("style_name", "van_gogh"))
        style_ref = request.parameters.get("style_reference")
        intensity = float(request.parameters.get("intensity", 0.75))
        out_img = self.apply_style(src, style_name=style_name, style_reference=style_ref, intensity=intensity)
        raw_bytes = encode_png(out_img)
        return build_artifact(
            request,
            raw_bytes,
            {
                "engine": "style_transfer",
                "style_name": style_name,
                "width": out_img.width,
                "height": out_img.height,
                "intensity": intensity,
            },
        )

