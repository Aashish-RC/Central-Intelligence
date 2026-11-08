"""
Prompt template catalog and parameter styling engine for Media Generation.
Allows parameterization, consistent aesthetic styles, and automated negative prompting.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from media_gen.core.models import MediaType


class PromptTemplate(BaseModel):
    id: str
    name: str
    media_type: MediaType
    prompt_pattern: str
    default_negative_prompt: Optional[str] = None
    default_parameters: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


DEFAULT_TEMPLATES: List[PromptTemplate] = [
    PromptTemplate(
        id="photo_portrait",
        name="Photorealistic Studio Portrait",
        media_type=MediaType.IMAGE,
        prompt_pattern="Award-winning 8k studio portrait of {subject}, 85mm lens, f/1.4, dramatic studio rim lighting, intricate facial details, realistic skin texture",
        default_negative_prompt="blurry, low quality, cartoon, 3d render, distorted anatomy, extra fingers",
        default_parameters={"width": 1024, "height": 1024, "aspect_ratio": "1:1", "steps": 30},
        tags=["portrait", "photorealism", "studio"],
    ),
    PromptTemplate(
        id="cinematic_scene",
        name="Cinematic 4K Concept Landscape",
        media_type=MediaType.IMAGE,
        prompt_pattern="Cinematic wide shot of {environment}, cinematic volumetric lighting, atmospheric fog, photorealistic, Unreal Engine 5 render, epic scale",
        default_negative_prompt="watermark, signature, oversaturated, amateur, cropped",
        default_parameters={"width": 1344, "height": 768, "aspect_ratio": "16:9", "steps": 35},
        tags=["landscape", "cinematic", "concept_art"],
    ),
    PromptTemplate(
        id="synthwave_bgm",
        name="Retro Synthwave Instrumental",
        media_type=MediaType.AUDIO,
        prompt_pattern="Upbeat 1980s retro synthwave instrumental track, analog synthesizers, punchy gated reverb drums, neon aesthetic, tempo {tempo} bpm",
        default_parameters={"duration_seconds": 30, "sample_rate": 44100, "tempo": 120},
        tags=["music", "synthwave", "instrumental"],
    ),
    PromptTemplate(
        id="cinematic_drone_shot",
        name="Cinematic Drone Flight Video",
        media_type=MediaType.VIDEO,
        prompt_pattern="Smooth cinematic drone aerial footage sweeping over {location}, golden hour light, high frame rate, crisp focus, 4k",
        default_parameters={"duration_seconds": 5, "fps": 24, "motion_bucket": 127},
        tags=["video", "aerial", "drone"],
    ),
]


class PromptTemplateRegistry:
    """In-memory catalog of reusable prompt templates."""

    def __init__(self, templates: Optional[List[PromptTemplate]] = None):
        self._templates: Dict[str, PromptTemplate] = {}
        initial = templates or DEFAULT_TEMPLATES
        for t in initial:
            self.register(t)

    def register(self, template: PromptTemplate) -> None:
        self._templates[template.id] = template

    def get(self, template_id: str) -> Optional[PromptTemplate]:
        return self._templates.get(template_id)

    def list_by_type(self, media_type: MediaType) -> List[PromptTemplate]:
        return [t for t in self._templates.values() if t.media_type == media_type]

    def render(self, template_id: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Renders prompt string by expanding variables into template pattern."""
        template = self.get(template_id)
        if not template:
            raise ValueError(f"Unknown prompt template '{template_id}'")

        rendered_prompt = template.prompt_pattern
        for key, val in variables.items():
            rendered_prompt = rendered_prompt.replace(f"{{{key}}}", str(val))

        params = dict(template.default_parameters)
        for k, v in variables.items():
            if k not in ["subject", "environment", "location"]:
                params[k] = v

        return {
            "prompt": rendered_prompt,
            "negative_prompt": template.default_negative_prompt,
            "parameters": params,
            "media_type": template.media_type,
        }
