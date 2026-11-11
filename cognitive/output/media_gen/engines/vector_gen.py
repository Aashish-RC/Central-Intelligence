"""Editable Vector Graphics (SVG) Generation Engine (L6 Feature 6.14)."""

from __future__ import annotations

import hashlib
import html

from cognitive.output.media_gen.engines._pil_helpers import (
    BaseMediaEngine,
    MediaArtifact,
    MediaRequest,
    MediaType,
    build_artifact,
)


class VectorGenerationEngine(BaseMediaEngine):
    """Generates clean, editable layered SVG graphics and logos from text prompts."""

    def supported_type(self) -> MediaType:
        return MediaType.IMAGE

    def generate_svg(
        self,
        prompt: str,
        width: int = 512,
        height: int = 512,
        primary_color: str = "#2563EB",
        accent_color: str = "#10B981",
    ) -> str:
        """Synthesize valid, layer-organized SVG markup derived from `prompt`."""
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        label = html.escape(" ".join(prompt.split()[:4]) or "Vector Logo")
        cx, cy = width // 2, height // 2
        radius = int(min(width, height) * 0.32)
        rot = int(digest[:4], 16) % 45

        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}">\n'
            f'  <defs>\n'
            f'    <linearGradient id="brandGrad" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{primary_color}" />\n'
            f'      <stop offset="100%" stop-color="{accent_color}" />\n'
            f'    </linearGradient>\n'
            f'  </defs>\n'
            f'  <g id="layer-background">\n'
            f'    <rect width="{width}" height="{height}" rx="24" fill="#0F172A" />\n'
            f'  </g>\n'
            f'  <g id="layer-emblem" transform="rotate({rot} {cx} {cy})">\n'
            f'    <circle cx="{cx}" cy="{cy}" r="{radius}" fill="url(#brandGrad)" opacity="0.92" />\n'
            f'    <polygon points="{cx},{cy - radius // 2} {cx + radius // 2},{cy + radius // 2} '
            f'{cx - radius // 2},{cy + radius // 2}" fill="#FFFFFF" opacity="0.9" />\n'
            f'  </g>\n'
            f'  <g id="layer-typography">\n'
            f'    <text x="{cx}" y="{height - 36}" text-anchor="middle" fill="#F8FAFC" '
            f'font-family="sans-serif" font-size="22" font-weight="bold">{label}</text>\n'
            f'  </g>\n'
            f'</svg>\n'
        )

    async def generate(self, request: MediaRequest) -> MediaArtifact:
        if request.media_type != MediaType.IMAGE:
            raise ValueError(f"VectorGenerationEngine cannot handle {request.media_type}")
        width = int(request.parameters.get("width", 512))
        height = int(request.parameters.get("height", 512))
        svg_str = self.generate_svg(
            prompt=request.prompt,
            width=width,
            height=height,
            primary_color=str(request.parameters.get("primary_color", "#2563EB")),
            accent_color=str(request.parameters.get("accent_color", "#10B981")),
        )
        raw_bytes = svg_str.encode("utf-8")
        return build_artifact(
            request,
            raw_bytes,
            {
                "engine": "vector_gen",
                "format": "svg",
                "width": width,
                "height": height,
                "prompt": request.prompt,
            },
            ext="svg",
            mime_type="image/svg+xml",
        )

