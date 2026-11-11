"""Image Variations Engine (L6 Feature 6.11)."""

from __future__ import annotations

from typing import List

from PIL import Image, ImageEnhance, ImageOps

from cognitive.output.media_gen.engines._pil_helpers import (
    BaseMediaEngine,
    MediaArtifact,
    MediaRequest,
    MediaType,
    build_artifact,
    encode_png,
    load_image_input,
)


class ImageVariationsEngine(BaseMediaEngine):
    """Produces controlled visual variations from a seed reference image."""

    def supported_type(self) -> MediaType:
        return MediaType.IMAGE

    def create_variations(
        self,
        source: Image.Image | bytes | str,
        count: int = 4,
    ) -> List[Image.Image]:
        img = load_image_input(source)
        count = max(1, min(16, count))
        variants: List[Image.Image] = []
        w, h = img.size

        for idx in range(count):
            cur = img.copy()
            if idx % 2 == 1:
                cur = ImageOps.mirror(cur)
            # Subtle crop-and-zoom + color/brightness perturbation per variant
            inset = min(w, h) // (18 + idx * 2)
            if inset > 0 and w > inset * 4 and h > inset * 4:
                cur = cur.crop((inset, inset, w - inset, h - inset)).resize((w, h), Image.Resampling.BICUBIC)
            cur = ImageEnhance.Color(cur).enhance(0.85 + 0.15 * ((idx + 1) % 3))
            cur = ImageEnhance.Brightness(cur).enhance(0.92 + 0.08 * idx)
            variants.append(cur)
        return variants

    async def generate_variations(self, request: MediaRequest, count: int = 4) -> List[MediaArtifact]:
        src = request.parameters.get("source_image")
        imgs = self.create_variations(src, count=count)
        artifacts: List[MediaArtifact] = []
        for idx, var_img in enumerate(imgs):
            raw = encode_png(var_img)
            artifacts.append(
                build_artifact(
                    request,
                    raw,
                    {
                        "engine": "variations",
                        "variant_index": idx,
                        "width": var_img.width,
                        "height": var_img.height,
                    },
                )
            )
        return artifacts

    async def generate(self, request: MediaRequest) -> MediaArtifact:
        count = int(request.parameters.get("count", 4))
        artifacts = await self.generate_variations(request, count=count)
        return artifacts[0]

