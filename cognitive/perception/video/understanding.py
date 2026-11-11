"""Temporal Video Understanding & Event Timeline Summarizer (L1 Feature 1.40)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from cognitive.perception.video.video_adapter import VideoAdapter, VideoIngestionResult


@dataclass
class VideoEvent:
    """Discrete temporal event observed in a video."""

    timestamp_seconds: float
    summary: str
    objects: List[str] = field(default_factory=list)
    scene: str = "general"


@dataclass
class VideoUnderstandingReport:
    """Timeline of events and cohesive narrative answer over a video."""

    filename: str
    duration_seconds: float
    summary: str
    answer: str
    timeline: List[VideoEvent] = field(default_factory=list)
    unique_objects: List[str] = field(default_factory=list)


class VideoUnderstandingEngine:
    """Builds temporal event timelines from extracted frames and answers questions about a video."""

    def __init__(self, video_adapter: Optional[VideoAdapter] = None) -> None:
        self.video_adapter = video_adapter or VideoAdapter()

    def understand_video(
        self,
        video_path: str | Path,
        question: str = "What happened in this video?",
        fps: float = 1.0,
        max_frames: int = 12,
    ) -> VideoUnderstandingReport:
        ingestion: VideoIngestionResult = self.video_adapter.ingest_video(
            video_path,
            fps=fps,
            max_frames=max_frames,
            prompt=f"Analyze this video frame to help answer: {question}",
        )
        timeline: List[VideoEvent] = []
        seen_objects: Dict[str, None] = {}
        for ts, analysis in ingestion.frame_analyses:
            for obj in analysis.detected_objects:
                seen_objects[obj] = None
            timeline.append(
                VideoEvent(
                    timestamp_seconds=ts,
                    summary=analysis.description.strip(),
                    objects=list(analysis.detected_objects),
                    scene=analysis.scene_classification,
                )
            )

        timeline_text = "; ".join(f"[{e.timestamp_seconds:.1f}s] {e.summary}" for e in timeline)
        summary = (
            f"Video '{ingestion.filename}' ({ingestion.duration_seconds:.1f}s, "
            f"{len(timeline)} sampled moments): {timeline_text}"
        )
        answer = f"Answer to '{question}': {summary}"
        return VideoUnderstandingReport(
            filename=ingestion.filename,
            duration_seconds=ingestion.duration_seconds,
            summary=summary,
            answer=answer,
            timeline=timeline,
            unique_objects=list(seen_objects.keys()),
        )

