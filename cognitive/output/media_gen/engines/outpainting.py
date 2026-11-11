"""Image Border Extension / Outpainting Engine (L6 Feature 6.10)."""

from __future__ import annotations

from PIL import Image, ImageFilter, ImageOps

from cognitive.output.media_gen.engines._pil_helpers import (
    BaseMediaEngine,
    MediaArtifact,
    MediaRequest,
    MediaType,
    build_artifact,
    encode_png,
    load_image_input,
)


class OutpaintingEngine(BaseMediaEngine):
    """Extends an image canvas beyond its original borders seamlessly."""

    def supported_type(self) -> MediaType:
        return MediaType.IMAGE

    def outpaint(
        self,
        source: Image.Image | bytes | str,
        target_width: int = 768,
        target_height: int = 768,
    ) -> Image.Image:
        img = load_image_input(source)
        target_width = max(target_width, img.width)
        target_height = max(target_height, img.height)

        # Build mirrored & softly blurred surrounding background canvas
        mirror_base = ImageOps.mirror(img)
        bg = img.resize((target_width, target_height), Image.Resampling.BICUBIC)
        mirror_scaled = mirror_base.resize((target_width, target_height), Image.Resampling.BICUBIC)
        bg = Image.blend(bg, mirror_scaled, alpha=0.45).filter(ImageFilter.GaussianBlur(radius=8))

        paste_x = (target_width - img.width) // 2
        paste_y = (target_height - img.height) // 2
        bg.paste(img, (paste_x, paste_y))
        return bg

    async def generate(self, request: MediaRequest) -> MediaArtifact:
        if request.media_type != MediaType.IMAGE:
            raise ValueError(f"OutpaintingEngine cannot handle {request.media_type}")
        src = request.parameters.get("source_image")
        tw = int(request.parameters.get("target_width", 768))
        th = int(request.parameters.get("target_height", 768))
        out_img = self.outpaint(src, target_width=tw, target_height=th)
        raw_bytes = encode_png(out_img)
        return build_artifact(
            request,
            raw_bytes,
            {
                "engine": "outpainting",
                "width": out_img.width,
                "height": out_img.height,
                "prompt": request.prompt,
            },
        )

