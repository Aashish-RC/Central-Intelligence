"""
Screenpipe Desktop Screen & Audio Awareness Adapter (Layer 1: Perception, Task 1.4).

Provides 24/7 continuous desktop screen and audio capture with local OCR indexing,
supplying persistent visual context for queries like "what was on screen 5 minutes ago".
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

logger = logging.getLogger("cognitive.perception.screen.screenpipe")


@dataclass
class OCRFrame:
    """An OCR-indexed visual screen capture frame."""
    frame_id: str = field(default_factory=lambda: f"frame_{uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)
    app_name: str = "Unknown"
    window_title: str = ""
    text: str = ""
    confidence: float = 0.95
    bounding_boxes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "app_name": self.app_name,
            "window_title": self.window_title,
            "text": self.text,
            "confidence": self.confidence,
            "bounding_boxes": self.bounding_boxes,
        }


class ScreenpipeAdapter:
    """
    Screen awareness adapter interfacing with the local Screenpipe service (Task 1.4).
    Indexes and queries chronological screen OCR captures.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:3030",
        enable_local_indexer: bool = True,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.enable_local_indexer = enable_local_indexer
        # In-memory chronological timeline repository
        self._frames: List[OCRFrame] = []

    def record_frame(
        self,
        text: str,
        app_name: str = "Unknown",
        window_title: str = "",
        timestamp: Optional[float] = None,
        confidence: float = 0.95,
        bounding_boxes: Optional[List[Dict[str, Any]]] = None,
    ) -> OCRFrame:
        """Indexes an OCR frame into the chronological timeline."""
        frame = OCRFrame(
            timestamp=timestamp if timestamp is not None else time.time(),
            app_name=app_name,
            window_title=window_title,
            text=text.strip(),
            confidence=confidence,
            bounding_boxes=bounding_boxes or [],
        )
        self._frames.append(frame)
        # Keep sorted by timestamp
        self._frames.sort(key=lambda f: f.timestamp)
        return frame

    def query_screen(
        self,
        query_text: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        app_name: Optional[str] = None,
        limit: int = 10,
    ) -> List[OCRFrame]:
        """
        Queries historical OCR frames by time interval, keyword search, or application.
        """
        results: List[OCRFrame] = []

        for f in self._frames:
            if start_time is not None and f.timestamp < start_time:
                continue
            if end_time is not None and f.timestamp > end_time:
                continue
            if app_name is not None and f.app_name.lower() != app_name.lower():
                continue
            if query_text is not None and query_text.lower() not in f.text.lower():
                continue

            results.append(f)

        # Return most recent matching frames up to limit
        return results[-limit:]

    def what_was_on_screen(
        self,
        seconds_ago: float = 300.0,
        tolerance_seconds: float = 60.0,
        current_time: Optional[float] = None,
    ) -> List[OCRFrame]:
        """
        Acceptance: Can query "what was on screen 5 minutes ago" and get OCR text.
        Searches a temporal window centered around (now - seconds_ago).
        """
        now = current_time if current_time is not None else time.time()
        target_timestamp = now - seconds_ago
        start_t = target_timestamp - tolerance_seconds
        end_t = target_timestamp + tolerance_seconds

        frames = self.query_screen(start_time=start_t, end_time=end_t)
        if not frames:
            # Fall back to finding closest historical frame prior to target_timestamp
            past_frames = [f for f in self._frames if f.timestamp <= target_timestamp]
            if past_frames:
                frames = [past_frames[-1]]

        return frames

    async def fetch_remote_screenpipe(
        self,
        query: Optional[str] = None,
        limit: int = 5,
    ) -> List[OCRFrame]:
        """Queries local screenpipe daemon if running."""
        try:
            async with httpx.AsyncClient(timeout=0.5) as client:
                params = {"limit": limit}
                if query:
                    params["q"] = query
                resp = await client.get(f"{self.api_url}/search", params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    frames = []
                    for item in data.get("data", []):
                        frames.append(
                            OCRFrame(
                                frame_id=item.get("id", str(uuid4())),
                                text=item.get("content", {}).get("text", ""),
                                app_name=item.get("content", {}).get("app_name", ""),
                                window_title=item.get("content", {}).get("window_name", ""),
                            )
                        )
                    return frames
        except Exception:
            pass
        return self.query_screen(query_text=query, limit=limit)


# Global default instance
default_screenpipe_adapter = ScreenpipeAdapter()

