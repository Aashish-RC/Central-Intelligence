"""Parallel Batch Document Processor (L1 Feature 1.20)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from cognitive.perception.document.unstructured_adapter import ParsedDocument, UnstructuredAdapter


@dataclass
class BatchDocumentResult:
    """Outcome summary across a parallel batch of parsed documents."""

    total: int
    succeeded: int
    failed: int
    documents: List[ParsedDocument] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)


class BatchDocumentProcessor:
    """Processes multiple documents concurrently via bounded asyncio thread-pool execution."""

    def __init__(
        self,
        adapter: Optional[UnstructuredAdapter] = None,
        max_concurrency: int = 8,
    ) -> None:
        self.adapter = adapter or UnstructuredAdapter()
        self.max_concurrency = max(1, max_concurrency)

    async def process_batch(
        self,
        file_paths: Sequence[str | Path],
    ) -> BatchDocumentResult:
        semaphore = asyncio.Semaphore(self.max_concurrency)
        docs: List[Optional[ParsedDocument]] = [None] * len(file_paths)
        errors: Dict[str, str] = {}

        async def _worker(idx: int, target: str | Path) -> None:
            async with semaphore:
                try:
                    docs[idx] = await asyncio.to_thread(self.adapter.parse_document, target)
                except Exception as exc:
                    errors[str(target)] = str(exc)

        await asyncio.gather(*(_worker(i, p) for i, p in enumerate(file_paths)))
        completed = [d for d in docs if d is not None]
        return BatchDocumentResult(
            total=len(file_paths),
            succeeded=len(completed),
            failed=len(errors),
            documents=completed,
            errors=errors,
        )

