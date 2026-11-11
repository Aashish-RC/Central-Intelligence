"""Automatic Modality Fallback Router (L1 Feature 1.45)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Set


@dataclass
class ModelCapabilityProfile:
    """Declares which input modalities an upstream model natively accepts."""

    model_id: str
    supported_modalities: Set[str] = field(default_factory=lambda: {"text"})


@dataclass
class FallbackConversionResult:
    """Normalized text representation returned when native modality is unsupported."""

    original_modality: str
    target_modality: str
    converted_text: str
    fallback_applied: bool
    converter_used: str


class ModalityFallbackRouter:
    """Translates unsupported modalities into text context before L4/gateway dispatch."""

    def __init__(self) -> None:
        self._converters: Dict[str, Callable[[object], str]] = {}

    def register_converter(self, modality: str, converter_fn: Callable[[object], str]) -> None:
        self._converters[modality.lower()] = converter_fn

    def route(
        self,
        modality: str,
        payload: object,
        model_profile: ModelCapabilityProfile,
    ) -> FallbackConversionResult:
        mod = modality.lower()
        supported = {m.lower() for m in model_profile.supported_modalities}
        if mod in supported:
            return FallbackConversionResult(
                original_modality=mod,
                target_modality=mod,
                converted_text=str(payload) if mod == "text" else "",
                fallback_applied=False,
                converter_used="native_passthrough",
            )

        if mod in self._converters:
            text_out = self._converters[mod](payload)
            return FallbackConversionResult(
                original_modality=mod,
                target_modality="text",
                converted_text=text_out,
                fallback_applied=True,
                converter_used=f"registered:{mod}_to_text",
            )

        if mod == "image":
            return FallbackConversionResult(
                original_modality="image",
                target_modality="text",
                converted_text=f"[Image caption/OCR fallback for payload type {type(payload).__name__}]",
                fallback_applied=True,
                converter_used="default_image_to_text",
            )
        if mod == "audio":
            return FallbackConversionResult(
                original_modality="audio",
                target_modality="text",
                converted_text=f"[Speech transcript fallback for audio payload]",
                fallback_applied=True,
                converter_used="default_audio_to_text",
            )
        return FallbackConversionResult(
            original_modality=mod,
            target_modality="text",
            converted_text=str(payload),
            fallback_applied=True,
            converter_used="stringify_fallback",
        )

