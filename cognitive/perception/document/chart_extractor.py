"""Chart & Graph Data Extractor -> Structured JSON Series (L1 Feature 1.18)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image

from cognitive.perception.vision.vlm_client import VLMClient


@dataclass
class ChartDataPoint:
    """Single labeled value extracted from a chart or graph."""

    label: str
    value: float
    series: str = "default"


@dataclass
class ChartExtractionResult:
    """Structured chart specification and extracted series data."""

    chart_type: str
    title: str = ""
    points: List[ChartDataPoint] = field(default_factory=list)
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chart_type": self.chart_type,
            "title": self.title,
            "points": [
                {"label": p.label, "value": p.value, "series": p.series} for p in self.points
            ],
        }


class ChartExtractor:
    """Extracts structured data points from bar, line, and pie chart images."""

    def __init__(self, vlm_client: Optional[VLMClient] = None) -> None:
        self.vlm_client = vlm_client or VLMClient(_defer_prod_check=True)

    @staticmethod
    def parse_structured_output(raw_text: str) -> ChartExtractionResult:
        cleaned = raw_text.strip()
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                pts = [
                    ChartDataPoint(
                        label=str(p["label"]),
                        value=float(p["value"]),
                        series=str(p.get("series", "default")),
                    )
                    for p in data.get("points", [])
                    if "label" in p and "value" in p
                ]
                return ChartExtractionResult(
                    chart_type=str(data.get("chart_type", "bar")),
                    title=str(data.get("title", "")),
                    points=pts,
                    raw_text=cleaned,
                )
        except Exception:
            pass

        # Fallback key: numeric parser (e.g. "Q1: 120, Q2: 185")
        pts = [
            ChartDataPoint(label=m.group(1).strip(), value=float(m.group(2)))
            for m in re.finditer(r"([A-Za-z0-9_\- ]+)\s*[:=]\s*(-?\d+(?:\.\d+)?)", cleaned)
        ]
        return ChartExtractionResult(chart_type="unknown", points=pts, raw_text=cleaned)

    def extract(
        self,
        image_input: Union[str, Path, bytes, Image.Image],
        chart_hint: str = "bar",
    ) -> ChartExtractionResult:
        res = self.vlm_client.analyze_image(
            image_input,
            prompt=(
                f"Extract the data points from this {chart_hint} chart as JSON with keys "
                "'chart_type', 'title', and 'points' ([{\"label\": ..., \"value\": ...}])."
            ),
        )
        parsed = self.parse_structured_output(res.description)
        if parsed.chart_type == "unknown":
            parsed.chart_type = chart_hint
        return parsed

