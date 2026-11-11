"""Super-Resolution Image Upscaling Engine (L6 Feature 6.13)."""

from __future__ import annotations

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


class UpscalingEngine(BaseMediaEngine):
    """Increases image resolution via Lanczos super-resolution + detail sharpening."""

    def supported_type(self) -> MediaType:
        return MediaType.IMAGE

    def upscale(
        self,
        source: Image.Image | bytes | str,
        scale_factor: int = 4,
    ) -> Image.Image:
        img = load_image_input(source)
        scale_factor = max(1, min(8, int(scale_factor)))
        new_size = (img.width * scale_factor, img.height * scale_factor)
        upscaled = img.resize(new_size, Image.Resampling.LANCZOS)
        return upscaled.filter(ImageFilter.UnsharpMask(radius=1.5, percent=125, threshold=3))

    async def generate(self, request: MediaRequest) -> MediaArtifact:
        if request.media_type != MediaType.IMAGE:
            raise ValueError(f"UpscalingEngine cannot handle {request.media_type}")
        src = request.parameters.get("source_image")
        scale = int(request.parameters.get("scale_factor", 4))
        out_img = self.upscale(src, scale_factor=scale)
        raw_bytes = encode_png(out_img)
        return build_artifact(
            request,
            raw_bytes,
            {
                "engine": "upscaling",
                "scale_factor": scale,
                "width": out_img.width,
                "height": out_img.height,
            },
        )

