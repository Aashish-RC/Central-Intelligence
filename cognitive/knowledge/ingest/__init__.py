"""L3 Knowledge multi-modal ingestion package."""

from cognitive.knowledge.ingest._store import InMemoryKnowledgeIndex, KnowledgeChunk, KnowledgeHit
from cognitive.knowledge.ingest.audio_video import AudioVideoIngestor, MediaIngestionResult
from cognitive.knowledge.ingest.email import EmailIngestor, ParsedEmail
from cognitive.knowledge.ingest.image_ingest import ImageIngestor, IngestedImage
from cognitive.knowledge.ingest.version_tracker import DiffSummary, SourceVersionTracker
from cognitive.knowledge.ingest.video_transcript import TranscriptSegment, VideoTranscriptIngestor

__all__ = [
    "AudioVideoIngestor",
    "DiffSummary",
    "EmailIngestor",
    "ImageIngestor",
    "InMemoryKnowledgeIndex",
    "IngestedImage",
    "KnowledgeChunk",
    "KnowledgeHit",
    "MediaIngestionResult",
    "ParsedEmail",
    "SourceVersionTracker",
    "TranscriptSegment",
    "VideoTranscriptIngestor",
]

