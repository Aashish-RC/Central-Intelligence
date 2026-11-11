"""Video Transcript Ingestion Engine (L3 Feature 3.03).

Parses SRT and WebVTT transcripts (e.g., YouTube captions), chunks cues with
timecodes preserved in metadata, and indexes them into the searchable store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from cognitive.knowledge.ingest._store import InMemoryKnowledgeIndex, KnowledgeChunk, KnowledgeHit


_TIMECODE_RE = re.compile(
    r"(?P<start>\d{1,2}:?\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{1,2}:?\d{2}:\d{2}[,.]\d{3})"
)


@dataclass
class TranscriptSegment:
    """Single caption cue extracted from SRT or VTT."""

    index: int
    start_time: str
    end_time: str
    text: str


class VideoTranscriptIngestor:
    """Parses and indexes SRT/VTT video transcripts for retrieval."""

    def __init__(self, index: Optional[InMemoryKnowledgeIndex] = None) -> None:
        self.index = index or InMemoryKnowledgeIndex()

    @staticmethod
    def parse_transcript(content: str) -> List[TranscriptSegment]:
        """Parse both SRT and WebVTT transcript formats into segments."""
        lines = content.replace("\r\n", "\n").splitlines()
        segments: List[TranscriptSegment] = []
        i = 0
        seg_num = 1
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.upper().startswith("WEBVTT") or line.startswith("NOTE"):
                i += 1
                continue
            # Optional numeric cue index before timestamp
            if line.isdigit() and i + 1 < len(lines) and _TIMECODE_RE.search(lines[i + 1]):
                i += 1
                line = lines[i].strip()

            m = _TIMECODE_RE.search(line)
            if m:
                start_t, end_t = m.group("start").replace(",", "."), m.group("end").replace(",", ".")
                i += 1
                text_lines: List[str] = []
                while i < len(lines) and lines[i].strip():
                    # Strip simple VTT styling tags such as <c> or <b>
                    cleaned = re.sub(r"<[^>]+>", "", lines[i].strip())
                    if cleaned:
                        text_lines.append(cleaned)
                    i += 1
                if text_lines:
                    segments.append(
                        TranscriptSegment(
                            index=seg_num,
                            start_time=start_t,
                            end_time=end_t,
                            text=" ".join(text_lines),
                        )
                    )
                    seg_num += 1
            else:
                i += 1
        return segments

    def ingest(
        self,
        source_id: str,
        transcript_text: str,
        title: str = "",
        window_segments: int = 3,
    ) -> List[KnowledgeChunk]:
        """Parse transcript cues, group into retrieval chunks, and index them."""
        segments = self.parse_transcript(transcript_text)
        self.index.delete_source(source_id)
        chunks: List[KnowledgeChunk] = []

        step = max(1, window_segments)
        for pos in range(0, len(segments), step):
            group = segments[pos : pos + step]
            combined_text = " ".join(seg.text for seg in group)
            chunk = KnowledgeChunk(
                chunk_id=f"{source_id}:t:{pos}",
                source_id=source_id,
                modality="video_transcript",
                text=combined_text,
                metadata={
                    "title": title,
                    "start_time": group[0].start_time,
                    "end_time": group[-1].end_time,
                    "cue_count": len(group),
                },
            )
            self.index.add(chunk)
            chunks.append(chunk)
        return chunks

    def search(self, query: str, top_k: int = 5) -> List[KnowledgeHit]:
        return self.index.search(query, top_k=top_k, modality="video_transcript")

