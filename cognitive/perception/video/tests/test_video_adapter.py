"""Unit tests for L1 Video Input (1.04) and Video Understanding (1.40)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from cognitive.perception.video.understanding import VideoUnderstandingEngine
from cognitive.perception.video.video_adapter import VideoAdapter
from cognitive.perception.vision.vlm_client import VLMAnalysisResult, VLMClient


def test_video_adapter_and_understanding(tmp_path: Path) -> None:
    vid = tmp_path / "sample.mp4"
    vid.write_bytes(b"\x00\x00\x00\x18ftypmp42DURATION=10.0;" + b"\x11\x22\x33" * 200)

    mock_vlm = MagicMock(spec=VLMClient)
    mock_vlm.analyze_image.side_effect = [
        VLMAnalysisResult(description="A presenter walks onto stage", detected_objects=["person"], scene_classification="indoor"),
        VLMAnalysisResult(description="Slides are displayed on screen", detected_objects=["screen"], scene_classification="indoor"),
    ]

    adapter = VideoAdapter(vlm_client=mock_vlm)
    ingestion = adapter.ingest_video(vid, fps=0.2, max_frames=2)
    assert ingestion.duration_seconds == 10.0
    assert len(ingestion.frames) == 2

    mock_vlm.analyze_image.side_effect = [
        VLMAnalysisResult(description="User opened dashboard", detected_objects=["laptop"], scene_classification="office"),
        VLMAnalysisResult(description="Chart finished rendering", detected_objects=["chart"], scene_classification="office"),
    ]
    engine = VideoUnderstandingEngine(video_adapter=VideoAdapter(vlm_client=mock_vlm))
    report = engine.understand_video(vid, question="What happened in this video?", fps=0.2, max_frames=2)
    assert "What happened in this video?" in report.answer
    assert "User opened dashboard" in report.summary
    assert "laptop" in report.unique_objects

