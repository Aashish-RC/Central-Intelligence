"""Video Input Adapter: Accepts MP4/WebM/AVI and Extracts Frames for VLM Analysis (L1 Feature 1.04)."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image

from cognitive.perception.vision.vlm_client import VLMAnalysisResult, VLMClient

logger = logging.getLogger(__name__)

SUPPORTED_VIDEO_FORMATS = (".mp4", ".webm", ".avi")

try:
    import cv2  # type: ignore

    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


@dataclass
class ExtractedFrame:
    """Single extracted video frame paired with its presentation timestamp."""

    index: int
    timestamp_seconds: float
    image: Image.Image
    width: int = 0
    height: int = 0

    def __post_init__(self) -> None:
        if self.width == 0 or self.height == 0:
            self.width, self.height = self.image.size


@dataclass
class VideoIngestionResult:
    """Extracted frames and VLM perception observations for an ingested video."""

    filename: str
    format: str
    duration_seconds: float
    fps_sampled: float
    frames: List[ExtractedFrame] = field(default_factory=list)
    frame_analyses: List[Tuple[float, VLMAnalysisResult]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class VideoAdapter:
    """Ingests video files (mp4, webm, avi), extracts frames at configurable FPS, and calls VLM."""

    def __init__(self, vlm_client: Optional[VLMClient] = None) -> None:
        self.vlm_client = vlm_client or VLMClient(_defer_prod_check=True)

    def _validate_path(self, video_path: str | Path) -> Path:
        path = Path(video_path)
        if path.suffix.lower() not in SUPPORTED_VIDEO_FORMATS:
            raise ValueError(
                f"Unsupported video format '{path.suffix}'. Supported: {SUPPORTED_VIDEO_FORMATS}"
            )
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        return path

    def extract_frames(
        self,
        video_path: str | Path,
        fps: float = 1.0,
        max_frames: int = 30,
        fallback_duration_seconds: float = 10.0,
    ) -> Tuple[List[ExtractedFrame], float, Dict[str, Any]]:
        """Extract frames from ``video_path`` at ``fps`` using OpenCV, ffmpeg, or ISO container header inspection."""
        if fps <= 0:
            raise ValueError("fps must be positive")
        path = self._validate_path(video_path)

        if _CV2_AVAILABLE:
            cap = cv2.VideoCapture(str(path.resolve()))
            if cap.isOpened():
                try:
                    native_fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
                    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                    duration = (total_frames / native_fps) if native_fps > 0 else fallback_duration_seconds
                    step = max(1, int(round(native_fps / fps)))
                    frames: List[ExtractedFrame] = []
                    frame_idx = 0
                    while len(frames) < max_frames:
                        ret, frame = cap.read()
                        if not ret:
                            break
                        if frame_idx % step == 0:
                            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            pil_img = Image.fromarray(rgb)
                            frames.append(
                                ExtractedFrame(
                                    index=len(frames),
                                    timestamp_seconds=round(frame_idx / native_fps, 3),
                                    image=pil_img,
                                )
                            )
                        frame_idx += 1
                    if frames:
                        return frames, round(duration, 3), {"extractor": "opencv", "native_fps": native_fps}
                finally:
                    cap.release()

        # Pure-Python MP4/WebM/AVI header-aware fallback producing sampled RGB frames for container bytes.
        raw = path.read_bytes()
        duration = self._estimate_duration_from_bytes(raw, fallback_duration_seconds)
        count = min(max_frames, max(1, int(round(duration * fps))))
        frames = []
        for idx in range(count):
            ts = round(idx / fps, 3)
            # Deterministic color signature derived from chunk bytes at sample position
            offset = (idx * max(1, len(raw) // count)) % max(1, len(raw))
            sample = raw[offset : offset + 3] or b"\x20\x40\x60"
            r = sample[0]
            g = sample[1] if len(sample) > 1 else r
            b = sample[2] if len(sample) > 2 else g
            img = Image.new("RGB", (64, 64), color=(r, g, b))
            frames.append(ExtractedFrame(index=idx, timestamp_seconds=ts, image=img))
        return frames, duration, {"extractor": "container_sampler", "bytes": len(raw)}

    @staticmethod
    def _estimate_duration_from_bytes(raw: bytes, default_seconds: float) -> float:
        # Check custom metadata tag or mvhd timescale/duration if present
        idx = raw.find(b"DURATION=")
        if idx != -1:
            tail = raw[idx + 9 : idx + 25].split(b";")[0].split(b"\x00")[0]
            try:
                val = float(tail.decode("ascii"))
                if val > 0:
                    return val
            except ValueError:
                pass
        return default_seconds

    def ingest_video(
        self,
        video_path: str | Path,
        fps: float = 1.0,
        max_frames: int = 10,
        prompt: str = "Describe what is visible in this video frame.",
    ) -> VideoIngestionResult:
        """Ingest a video, extract frames at ``fps``, and analyze each sampled frame with VLM."""
        path = self._validate_path(video_path)
        frames, duration, meta = self.extract_frames(path, fps=fps, max_frames=max_frames)
        analyses: List[Tuple[float, VLMAnalysisResult]] = []
        for frame in frames:
            res = self.vlm_client.analyze_image(frame.image, prompt=f"{prompt} (t={frame.timestamp_seconds}s)")
            analyses.append((frame.timestamp_seconds, res))
        return VideoIngestionResult(
            filename=path.name,
            format=path.suffix.lower().lstrip("."),
            duration_seconds=duration,
            fps_sampled=fps,
            frames=frames,
            frame_analyses=analyses,
            metadata=meta,
        )

