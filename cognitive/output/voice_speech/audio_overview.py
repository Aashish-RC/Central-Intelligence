"""Two-Host Audio Overview Generator (L6 Feature 6.19).

Synthesizes a two-host podcast-style dialogue summarizing source documents and
compiles individual spoken turns into a single valid WAV audio stream.
"""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass, field
from typing import List, Optional

from cognitive.output.voice_speech.core.models import AudioFormat, SpeechSynthesisRequest
from cognitive.output.voice_speech.tts.synthesis_engine import SpeechSynthesizer


@dataclass
class DialogueTurn:
    """Single conversational turn assigned to one podcast host."""

    speaker: str
    voice_id: str
    text: str


@dataclass
class AudioOverviewResult:
    """Complete two-host audio overview script + synthesized WAV buffer."""

    title: str
    script: List[DialogueTurn] = field(default_factory=list)
    audio_bytes: bytes = b""
    estimated_duration_seconds: float = 0.0
    sample_rate: int = 24000


class AudioOverviewGenerator:
    """Generates two-host spoken summaries of source texts or research papers."""

    def __init__(
        self,
        synthesizer: Optional[SpeechSynthesizer] = None,
        host_a_voice: str = "aura-orpheus",
        host_b_voice: str = "aura-asteria",
    ) -> None:
        self.synthesizer = synthesizer or SpeechSynthesizer()
        self.host_a_voice = host_a_voice
        self.host_b_voice = host_b_voice

    def generate_script(
        self,
        sources: List[str],
        title: str = "Research Overview",
        target_duration_seconds: int = 120,
    ) -> List[DialogueTurn]:
        """Turn source excerpts into alternating Host A / Host B dialogue."""
        sentences: List[str] = []
        for src in sources:
            for part in src.replace("?", ".").replace("!", ".").split("."):
                clean = part.strip()
                if len(clean) >= 12:
                    sentences.append(clean)
        if not sentences:
            sentences = ["Here are the primary highlights from the provided research source."]

        turns: List[DialogueTurn] = [
            DialogueTurn(
                speaker="Host A",
                voice_id=self.host_a_voice,
                text=f"Welcome to this audio overview of {title}. Let's unpack the main findings.",
            ),
            DialogueTurn(
                speaker="Host B",
                voice_id=self.host_b_voice,
                text=f"Glad to be here! What stood out right away from the paper was: {sentences[0]}.",
            ),
        ]

        # Expand dialogue turns evenly to cover key source points up to target word budget (~2.5 words/sec)
        target_words = max(40, int(target_duration_seconds * 2.5))
        current_words = sum(len(t.text.split()) for t in turns)
        idx = 1
        while current_words < target_words and idx < max(len(sentences), 8):
            fact = sentences[idx % len(sentences)]
            if idx % 2 == 1:
                line = f"Exactly, and building on that point, the study specifically shows that {fact}."
                speaker, voice = "Host A", self.host_a_voice
            else:
                line = f"Right, which has direct practical implications because {fact}."
                speaker, voice = "Host B", self.host_b_voice
            turns.append(DialogueTurn(speaker=speaker, voice_id=voice, text=line))
            current_words += len(line.split())
            idx += 1

        turns.append(
            DialogueTurn(
                speaker="Host B",
                voice_id=self.host_b_voice,
                text=f"Thanks for listening to our breakdown of {title}.",
            )
        )
        return turns

    @staticmethod
    def _concat_wav_chunks(wav_chunks: List[bytes]) -> tuple[bytes, int]:
        """Concatenate multiple RIFF WAV payloads (or raw frames fallback) into a single WAV."""
        frames: List[bytes] = []
        params = (1, 2, 24000)  # nchannels, sampwidth, framerate
        for chunk in wav_chunks:
            if len(chunk) > 44 and chunk[:4] == b"RIFF":
                try:
                    with wave.open(io.BytesIO(chunk), "rb") as w_in:
                        params = (w_in.getnchannels(), w_in.getsampwidth(), w_in.getframerate())
                        frames.append(w_in.readframes(w_in.getnframes()))
                    continue
                except wave.Error:
                    pass
            if chunk:
                frames.append(chunk)

        out_buf = io.BytesIO()
        with wave.open(out_buf, "wb") as w_out:
            w_out.setnchannels(params[0])
            w_out.setsampwidth(params[1])
            w_out.setframerate(params[2])
            w_out.writeframes(b"".join(frames))
        return out_buf.getvalue(), params[2]

    def generate_overview(
        self,
        sources: List[str],
        title: str = "Research Overview",
        target_duration_seconds: int = 120,
    ) -> AudioOverviewResult:
        """Create two-host script, synthesize turns, and return unified WAV overview."""
        turns = self.generate_script(
            sources=sources,
            title=title,
            target_duration_seconds=target_duration_seconds,
        )
        wav_parts: List[bytes] = []
        total_duration = 0.0
        for turn in turns:
            syn = self.synthesizer.synthesize(
                SpeechSynthesisRequest(
                    text=turn.text,
                    voice_id=turn.voice_id,
                    audio_format=AudioFormat.WAV,
                )
            )
            wav_parts.append(syn.audio_bytes)
            total_duration += syn.duration_seconds

        combined_wav, sr = self._concat_wav_chunks(wav_parts)
        return AudioOverviewResult(
            title=title,
            script=turns,
            audio_bytes=combined_wav,
            estimated_duration_seconds=round(total_duration, 2),
            sample_rate=sr,
        )

