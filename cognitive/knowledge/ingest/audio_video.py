"""Audio & Video Content Ingestion Pipeline (L3 Feature 3.04).

Extracts transcripts from audio/video files via L1 speech/video adapters
and indexes timestamped knowledge chunks into the L3 retrieval store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from cognitive.knowledge.ingest._store import InMemoryKnowledgeIndex, KnowledgeChunk, KnowledgeHit


@dataclass
class MediaIngestionResult:
    """Summary of audio/video transcription + indexing."""

    source_id: str
    media_type: str
    transcript: str
    chunks_indexed: int
    language: str = "en"
    chunk_ids: List[str] = field(default_factory=list)


class AudioVideoIngestor:
    """Ingests audio (MP3/WAV) or video files using L1 perception adapters."""

    def __init__(
        self,
        index: Optional[InMemoryKnowledgeIndex] = None,
        speech_adapter: Optional[Any] = None,
    ) -> None:
        self.index = index or InMemoryKnowledgeIndex()
        self._speech_adapter = speech_adapter

    def _get_speech_adapter(self) -> Any:
        if self._speech_adapter is None:
            from cognitive.perception.audio.handy_adapter import HandySpeechAdapter
            self._speech_adapter = HandySpeechAdapter(_defer_prod_check=True)
        return self._speech_adapter

    def ingest_audio(
        self,
        source_id: str,
        audio_source: str | Path | bytes,
        title: str = "",
        transcript_override: Optional[str] = None,
    ) -> MediaIngestionResult:
        """Transcribe an audio file/buffer via L1 speech adapter and index segments."""
        transcript_text = transcript_override or ""
        language = "en"
        segments_raw: List[str] = []

        if not transcript_text:
            adapter = self._get_speech_adapter()
            if isinstance(audio_source, bytes):
                out = adapter.transcribe_bytes(audio_source)
            else:
                out = adapter.transcribe_file(str(audio_source))
            transcript_text = out.text
            language = getattr(out, "language", "en")
            segs = getattr(out, "segments", None) or []
            for seg in segs:
                seg_txt = seg.get("text", "").strip() if isinstance(seg, dict) else getattr(seg, "text", "").strip()
                if seg_txt:
                    segments_raw.append(seg_txt)

        if not segments_raw and transcript_text:
            # Split long transcript into ~sentence groups for clean retrieval chunks
            sentences = [s.strip() for s in transcript_text.replace("?", ".").replace("!", ".").split(".") if s.strip()]
            for i in range(0, max(1, len(sentences)), 2):
                chunk_text = ". ".join(sentences[i : i + 2])
                if chunk_text:
                    segments_raw.append(chunk_text)

        self.index.delete_source(source_id)
        chunk_ids: List[str] = []
        for idx, text_part in enumerate(segments_raw):
            cid = f"{source_id}:av:{idx}"
            self.index.add(
                KnowledgeChunk(
                    chunk_id=cid,
                    source_id=source_id,
                    modality="audio_video",
                    text=text_part,
                    metadata={"title": title, "language": language, "segment_index": idx},
                )
            )
            chunk_ids.append(cid)

        return MediaIngestionResult(
            source_id=source_id,
            media_type="audio",
            transcript=transcript_text,
            chunks_indexed=len(chunk_ids),
            language=language,
            chunk_ids=chunk_ids,
        )

    def search(self, query: str, top_k: int = 5) -> List[KnowledgeHit]:
        return self.index.search(query, top_k=top_k, modality="audio_video")

