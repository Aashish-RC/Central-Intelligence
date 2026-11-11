"""Tests for Audio Vocabulary Biasing (1.24), Language Detection (1.25), and Code-Switching (1.26)."""

from __future__ import annotations

from cognitive.perception.audio.code_switching import CodeSwitchingHandler
from cognitive.perception.audio.handy_adapter import HandyAdapter, TranscriptionOutput
from cognitive.perception.audio.language_detector import AudioLanguageDetector
from cognitive.perception.audio.vocabulary_bias import CustomVocabularyBiaser


def test_vocabulary_bias_language_detector_and_code_switching(monkeypatch) -> None:
    # 1.24 Custom vocabulary biasing
    biaser = CustomVocabularyBiaser()
    biaser.register_terms(["hepatic", "bilirubin", "cholecystitis"])
    assert biaser.apply_correction("Elevated hepatik enzymes noted") == "Elevated hepatic enzymes noted"
    assert "hepatic" in biaser.build_whisper_prompt()

    # 1.25 Spoken language detection + model switch
    def fake_transcribe(self, audio_bytes: bytes, language=None):
        return TranscriptionOutput(
            text="Bonjour merci beaucoup avec plaisir",
            language=language or "en",
            duration_seconds=1.2,
        )

    monkeypatch.setattr(HandyAdapter, "transcribe_bytes", fake_transcribe)
    detector = AudioLanguageDetector(probe_adapter=HandyAdapter())
    detection, out = detector.detect_from_audio_and_transcribe(b"RIFF\x00\x00")
    assert detection.language == "fr"
    assert "fr" in detection.stt_model_id
    assert out.language == "fr"

    # 1.26 Code-switching within single sentence
    cs = CodeSwitchingHandler(primary_language="en")
    res = cs.normalize_mixed_utterance("I need to comprar groceries")
    assert res.transcript == "I need to comprar groceries"
    assert "en" in res.languages_present
    assert "es" in res.languages_present

