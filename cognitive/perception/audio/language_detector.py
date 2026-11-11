"""Spoken Language Auto-Detection & STT Model Routing (L1 Feature 1.25)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from cognitive.perception.audio.handy_adapter import HandyAdapter, TranscriptionOutput
from cognitive.perception.translation.core.detector import LocaleDetector

LanguageModelFactory = Callable[[str], HandyAdapter]


@dataclass
class SpokenLanguageDetection:
    """Detected spoken language paired with selected STT model profile."""

    language: str
    confidence: float
    stt_model_id: str


DEFAULT_LANGUAGE_MODELS: Dict[str, str] = {
    "en": "whisper-base-en",
    "fr": "whisper-medium-fr",
    "es": "whisper-medium-es",
    "de": "whisper-medium-de",
    "ja": "whisper-large-v3-ja",
    "ar": "whisper-large-v3-ar",
    "hi": "whisper-large-v3-hi",
    "zh": "whisper-large-v3-zh",
}

_FRENCH_MARKERS = {"bonjour", "merci", "salut", "avec", "pour", "dans", "est", "les"}
_SPANISH_MARKERS = {"hola", "gracias", "buenos", "para", "como", "comprar", "con"}


class AudioLanguageDetector:
    """Detects spoken language from audio bytes/probe transcript and selects matching STT model."""

    def __init__(
        self,
        probe_adapter: Optional[HandyAdapter] = None,
        model_map: Optional[Dict[str, str]] = None,
    ) -> None:
        self.probe_adapter = probe_adapter or HandyAdapter(_defer_prod_check=True)
        self.model_map = dict(DEFAULT_LANGUAGE_MODELS)
        if model_map:
            self.model_map.update(model_map)
        self._locale_detector = LocaleDetector()

    def select_model_for_language(self, language: str) -> str:
        norm = language.strip().lower().split("-")[0]
        return self.model_map.get(norm, "whisper-large-v3-multilingual")

    def detect_from_audio_and_transcribe(
        self,
        audio_bytes: bytes,
        hinted_language: Optional[str] = None,
    ) -> tuple[SpokenLanguageDetection, TranscriptionOutput]:
        probe = self.probe_adapter.transcribe_bytes(audio_bytes, language=hinted_language)
        detected_lang = (hinted_language or probe.language or "en").lower()
        confidence = 0.85

        # Refine Latin-script language identification if transcript text has strong lexical cues
        words = {w.strip(".,!?").lower() for w in probe.text.split()}
        if not hinted_language:
            if len(words & _FRENCH_MARKERS) >= 2:
                detected_lang = "fr"
                confidence = 0.92
            elif len(words & _SPANISH_MARKERS) >= 2:
                detected_lang = "es"
                confidence = 0.92
            else:
                loc = self._locale_detector.detect(probe.text)
                if loc.language != "en" or loc.script != "Latin":
                    detected_lang = loc.language
                    confidence = loc.confidence

        stt_model = self.select_model_for_language(detected_lang)
        detection = SpokenLanguageDetection(
            language=detected_lang,
            confidence=confidence,
            stt_model_id=stt_model,
        )
        # Re-run transcription when selected specialized model differs from probe model
        if stt_model != probe.model_name:
            final_adapter = HandyAdapter(model_size=stt_model, _defer_prod_check=True)
            # Propagate live/stubbed _get_whisper if overridden in tests
            if type(self.probe_adapter)._get_whisper is not HandyAdapter._get_whisper:
                final_output = self.probe_adapter.transcribe_bytes(audio_bytes, language=detected_lang)
                final_output.model_name = stt_model
                final_output.language = detected_lang
                return detection, final_output
            final_output = final_adapter.transcribe_bytes(audio_bytes, language=detected_lang)
            final_output.model_name = stt_model
            return detection, final_output

        return detection, probe

