"""Accessible Output Renderer (Feature 6.34)

Ensures multimedia and document outputs satisfy WCAG 2.2 AA accessibility requirements:
alt text for images, WebVTT/SRT captions for audio/video, and ARIA labels for screen readers.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AccessibleImageOutput:
    """Accessible representation of an image artifact."""
    src: str
    alt_text: str
    aria_label: str
    long_description: Optional[str] = None
    html_markup: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CaptionCue:
    """Single timed closed-caption cue."""
    start_time: float  # in seconds
    end_time: float
    text: str
    speaker: Optional[str] = None


@dataclass
class AccessibleAudioOutput:
    """Accessible representation of an audio artifact with synchronized captions."""
    audio_src: str
    title: str
    vtt_captions: str
    srt_captions: str
    transcript_text: str
    cues: List[CaptionCue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AccessibleOutputRenderer:
    """Renders accessible wrappers and subtitles for agent outputs."""

    def render_accessible_image(
        self,
        src: str,
        title: str,
        description: str,
        detected_elements: Optional[List[str]] = None,
        is_decorative: bool = False,
    ) -> AccessibleImageOutput:
        """Generate WCAG AA compliant image packaging with alt text and ARIA labels."""
        if is_decorative:
            return AccessibleImageOutput(
                src=src,
                alt_text="",
                aria_label="",
                html_markup=f'<img src="{src}" alt="" role="presentation" />',
                metadata={"decorative": True},
            )

        # Build informative alt text
        alt_parts = [title]
        if detected_elements:
            alt_parts.append(f"showing {', '.join(detected_elements)}")
        alt_text = f"{title}. {description}".strip()

        aria_label = f"Image: {title}"
        long_desc = description if len(description) > 100 else None

        markup_parts = [
            f'<figure role="group" aria-label="{aria_label}">',
            f'  <img src="{src}" alt="{alt_text}" role="img" aria-label="{aria_label}" />',
            f'  <figcaption>{title}</figcaption>',
            '</figure>',
        ]

        return AccessibleImageOutput(
            src=src,
            alt_text=alt_text,
            aria_label=aria_label,
            long_description=long_desc,
            html_markup="\n".join(markup_parts),
            metadata={"wcag_compliant": True},
        )

    def render_accessible_audio(
        self,
        audio_src: str,
        title: str,
        cues: List[CaptionCue],
    ) -> AccessibleAudioOutput:
        """Render audio payload with WebVTT and SRT captions and screen reader transcript."""
        vtt = self._build_vtt(cues)
        srt = self._build_srt(cues)
        transcript = " ".join([f"[{c.speaker}]: {c.text}" if c.speaker else c.text for c in cues])

        return AccessibleAudioOutput(
            audio_src=audio_src,
            title=title,
            vtt_captions=vtt,
            srt_captions=srt,
            transcript_text=transcript,
            cues=cues,
            metadata={"captions_format": ["vtt", "srt"], "wcag_compliant": True},
        )

    def _seconds_to_vtt_time(self, seconds: float) -> str:
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"

    def _seconds_to_srt_time(self, seconds: float) -> str:
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    def _build_vtt(self, cues: List[CaptionCue]) -> str:
        lines = ["WEBVTT", ""]
        for i, cue in enumerate(cues, start=1):
            start = self._seconds_to_vtt_time(cue.start_time)
            end = self._seconds_to_vtt_time(cue.end_time)
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            speaker_prefix = f"<v {cue.speaker}>" if cue.speaker else ""
            lines.append(f"{speaker_prefix}{cue.text}")
            lines.append("")
        return "\n".join(lines).strip()

    def _build_srt(self, cues: List[CaptionCue]) -> str:
        lines: List[str] = []
        for i, cue in enumerate(cues, start=1):
            start = self._seconds_to_srt_time(cue.start_time)
            end = self._seconds_to_srt_time(cue.end_time)
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            speaker_prefix = f"{cue.speaker}: " if cue.speaker else ""
            lines.append(f"{speaker_prefix}{cue.text}")
            lines.append("")
        return "\n".join(lines).strip()

