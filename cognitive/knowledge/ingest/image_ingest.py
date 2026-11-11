"""Image Ingestion with VLM Description & Metadata Indexing (L3 Feature 3.10)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image

from cognitive.knowledge.ingest._store import InMemoryKnowledgeIndex, KnowledgeChunk, KnowledgeHit
from cognitive.perception.vision.vlm_client import VLMClient


@dataclass
class IngestedImage:
    """Indexed image artifact containing structural metadata and VLM caption."""

    source_id: str
    width: int
    height: int
    format: str
    description: str
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ImageIngestor:
    """Generates textual descriptions via L1 VLMClient and indexes images for search."""

    def __init__(
        self,
        index: Optional[InMemoryKnowledgeIndex] = None,
        vlm_client: Optional[VLMClient] = None,
    ) -> None:
        self.index = index or InMemoryKnowledgeIndex()
        self.vlm_client = vlm_client or VLMClient(_defer_prod_check=True)

    def ingest(
        self,
        source_id: str,
        image_input: Union[str, Path, Image.Image],
        title: str = "",
        prompt: str = "Describe all key objects, text labels, and visual details for search indexing.",
    ) -> IngestedImage:
        """Analyze an image via VLM and index its metadata + generated description."""
        if isinstance(image_input, Image.Image):
            width, height = image_input.size
            fmt = image_input.format or "PNG"
        else:
            with Image.open(image_input) as img:
                width, height = img.size
                fmt = img.format or Path(image_input).suffix.lstrip(".").upper() or "PNG"

        vlm_res = self.vlm_client.analyze_image(image_input, prompt=prompt)
        description = vlm_res.description.strip()
        tags = list(vlm_res.detected_objects or [])

        self.index.delete_source(source_id)
        searchable = (
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Dimensions: {width}x{height} ({fmt})\n"
            + (f"Tags: {', '.join(tags)}" if tags else "")
        ).strip()

        self.index.add(
            KnowledgeChunk(
                chunk_id=f"{source_id}:image:0",
                source_id=source_id,
                modality="image",
                text=searchable,
                metadata={
                    "title": title,
                    "width": width,
                    "height": height,
                    "format": fmt,
                    "tags": tags,
                },
            )
        )
        return IngestedImage(
            source_id=source_id,
            width=width,
            height=height,
            format=fmt,
            description=description,
            tags=tags,
            metadata={"model": vlm_res.model_used},
        )

    def search(self, query: str, top_k: int = 5) -> List[KnowledgeHit]:
        return self.index.search(query, top_k=top_k, modality="image")

