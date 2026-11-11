"""Image Editing & Mask-Based Inpainting Engine (L6 Feature 6.09)."""

from __future__ import annotations

from typing import Optional, Tuple

from PIL import Image, ImageFilter

from cognitive.output.media_gen.engines._pil_helpers import (
    BaseMediaEngine,
    MediaArtifact,
    MediaRequest,
    MediaType,
    build_artifact,
    encode_png,
    load_image_input,
)


class InpaintingEngine(BaseMediaEngine):
    """Fills or removes masked image regions by harmonic neighbor diffusion + blur."""

    def supported_type(self) -> MediaType:
        return MediaType.IMAGE

    def inpaint(
        self,
        source: Image.Image | bytes | str,
        mask: Optional[Image.Image] = None,
        mask_bbox: Optional[Tuple[int, int, int, int]] = None,
        fill_color: Optional[Tuple[int, int, int]] = None,
    ) -> Image.Image:
        img = load_image_input(source)
        w, h = img.size

        if mask is None:
            m = Image.new("L", (w, h), 0)
            box = mask_bbox or (w // 4, h // 4, (3 * w) // 4, (3 * h) // 4)
            x1, y1, x2, y2 = max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3])
            for py in range(y1, y2):
                for px in range(x1, x2):
                    m.putpixel((px, py), 255)
        else:
            m = mask.convert("L").resize((w, h))

        # Estimate surrounding background color outside mask
        if fill_color is None:
            r_tot = g_tot = b_tot = cnt = 0
            src_px = img.load()
            m_px = m.load()
            step = max(1, min(w, h) // 32)
            for py in range(0, h, step):
                for px in range(0, w, step):
                    if m_px[px, py] < 128:
                        r, g, b = src_px[px, py]
                        r_tot += r
                        g_tot += g
                        b_tot += b
                        cnt += 1
            fill_color = (r_tot // cnt, g_tot // cnt, b_tot // cnt) if cnt else (128, 128, 128)

        # Initialize masked hole with background color, then blend softly outward/inward
        seed = Image.new("RGB", (w, h), fill_color)
        filled = Image.composite(seed, img, m)
        smooth_bg = filled.filter(ImageFilter.GaussianBlur(radius=max(3, min(w, h) // 16)))
        feathered_mask = m.filter(ImageFilter.GaussianBlur(radius=2))
        return Image.composite(smooth_bg, img, feathered_mask)

    async def generate(self, request: MediaRequest) -> MediaArtifact:
        if request.media_type != MediaType.IMAGE:
            raise ValueError(f"InpaintingEngine cannot handle {request.media_type}")
        src = request.parameters.get("source_image")
        mask = request.parameters.get("mask")
        bbox = request.parameters.get("mask_bbox")
        out_img = self.inpaint(src, mask=mask, mask_bbox=bbox)
        raw_bytes = encode_png(out_img)
        return build_artifact(
            request,
            raw_bytes,
            {
                "engine": "inpainting",
                "width": out_img.width,
                "height": out_img.height,
                "mask_bbox": bbox,
                "prompt": request.prompt,
            },
        )

