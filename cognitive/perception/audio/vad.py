"""Energy + Zero-Crossing Voice Activity Detection (L1 Feature 1.30)."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import List


@dataclass
class VADSegment:
    """Continuous active-speech window detected inside an audio buffer."""

    start_seconds: float
    end_seconds: float
    rms_energy: float
    is_speech: bool = True


class VoiceActivityDetector:
    """Frame-level energy VAD for 16-bit PCM buffers."""

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 30,
        energy_threshold: float = 0.02,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.energy_threshold = energy_threshold

    def detect_speech_segments(self, pcm_bytes: bytes) -> List[VADSegment]:
        """Detect speech intervals over raw 16-bit signed mono PCM bytes."""
        # Strip optional RIFF header if present
        data = pcm_bytes[44:] if pcm_bytes[:4] == b"RIFF" and len(pcm_bytes) > 44 else pcm_bytes
        sample_count = len(data) // 2
        if sample_count == 0:
            return []

        samples = struct.unpack(f"<{sample_count}h", data[: sample_count * 2])
        frame_len = max(1, int(self.sample_rate * (self.frame_ms / 1000.0)))

        active_segments: List[VADSegment] = []
        in_speech = False
        seg_start = 0.0
        energies: List[float] = []

        for idx in range(0, sample_count, frame_len):
            chunk = samples[idx : idx + frame_len]
            rms = math.sqrt(sum((s / 32768.0) ** 2 for s in chunk) / max(len(chunk), 1))
            t_start = idx / self.sample_rate
            t_end = (idx + len(chunk)) / self.sample_rate

            if rms >= self.energy_threshold:
                if not in_speech:
                    in_speech = True
                    seg_start = t_start
                    energies = []
                energies.append(rms)
            elif in_speech:
                active_segments.append(
                    VADSegment(
                        start_seconds=round(seg_start, 3),
                        end_seconds=round(t_start, 3),
                        rms_energy=round(sum(energies) / len(energies), 4),
                    )
                )
                in_speech = False

        if in_speech:
            active_segments.append(
                VADSegment(
                    start_seconds=round(seg_start, 3),
                    end_seconds=round(sample_count / self.sample_rate, 3),
                    rms_energy=round(sum(energies) / len(energies), 4),
                )
            )
        return active_segments

