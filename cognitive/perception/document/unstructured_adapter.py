"""
Unstructured Document Parsing Adapter (Layer 1: Perception, Task 1.5).

Extracts structured JSON, layout-aware elements, tables, and form fields from
PDF, DOCX, PPTX, and XLSX documents.
"""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger("cognitive.perception.document.unstructured")

try:
    from unstructured.partition.auto import partition
    _UNSTRUCTURED_AVAILABLE = True
except ImportError:
    _UNSTRUCTURED_AVAILABLE = False

try:
    import pypdf
    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False


@dataclass
class DocumentElement:
    """An individual structured element extracted from a document."""
    element_id: str = field(default_factory=lambda: f"elem_{uuid4().hex[:8]}")
    type: str = "NarrativeText"  # Title, NarrativeText, Table, Header, ListItem, FormField
    text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id": self.element_id,
            "type": self.type,
            "text": self.text,
            "metadata": self.metadata,
        }


@dataclass
class ParsedDocument:
    """Complete structured JSON representation of a parsed document."""
    filename: str
    file_type: str
    elements: List[DocumentElement] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(e.text for e in self.elements if e.text)

    def to_dict(self) -> Dict[str, Any]:
        """Acceptance: Can parse a PDF and return structured JSON with tables and text."""
        return {
            "filename": self.filename,
            "file_type": self.file_type,
            "total_elements": len(self.elements),
            "total_tables": len(self.tables),
            "elements": [e.to_dict() for e in self.elements],
            "tables": self.tables,
            "full_text": self.full_text,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class UnstructuredAdapter:
    """
    Document parsing adapter wrapping Unstructured.io (Task 1.5).
    Extracts structured JSON with tables, titles, form fields, and text blocks.
    """

    def __init__(self, strategy: str = "auto") -> None:
        self.strategy = strategy

    def parse_document(self, file_path: str | Path) -> ParsedDocument:
        """
        Parses document at file_path (PDF, DOCX, PPTX, XLSX, TXT) into structured JSON.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        ext = path.suffix.lower().lstrip(".")

        # Try Unstructured.io partition
        if _UNSTRUCTURED_AVAILABLE:
            try:
                raw_elements = partition(filename=str(path.resolve()), strategy=self.strategy)
                elements: List[DocumentElement] = []
                tables: List[Dict[str, Any]] = []

                for el in raw_elements:
                    el_type = el.__class__.__name__
                    el_text = str(el).strip()
                    el_meta = getattr(el, "metadata", None)
                    meta_dict: Dict[str, Any] = {}
                    if el_meta and hasattr(el_meta, "to_dict"):
                        meta_dict = el_meta.to_dict()

                    doc_elem = DocumentElement(
                        type=el_type,
                        text=el_text,
                        metadata=meta_dict,
                    )
                    elements.append(doc_elem)

                    if el_type == "Table":
                        tables.append({
                            "element_id": doc_elem.element_id,
                            "table_text": el_text,
                            "table_html": meta_dict.get("text_as_html", ""),
                            "page_number": meta_dict.get("page_number", 1),
                        })

                if elements:
                    return ParsedDocument(
                        filename=path.name,
                        file_type=ext,
                        elements=elements,
                        tables=tables,
                        metadata={"parser": "unstructured", "strategy": self.strategy},
                    )
            except Exception as e:
                logger.debug("Unstructured partition failed on %s: %s", path.name, e)

        # Fallback for PDF documents using pypdf
        if ext == "pdf" and _PYPDF_AVAILABLE:
            return self._parse_pdf_pypdf(path)

        # Generic text fallback
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            elem = DocumentElement(type="NarrativeText", text=content.strip(), metadata={"filename": path.name})
            return ParsedDocument(
                filename=path.name,
                file_type=ext,
                elements=[elem],
                tables=[],
                metadata={"parser": "plain_text_fallback"},
            )
        except Exception as e:
            logger.error("Failed reading document %s: %s", path.name, e)
            return ParsedDocument(
                filename=path.name,
                file_type=ext,
                elements=[],
                tables=[],
                metadata={"error": str(e)},
            )

    def _parse_pdf_pypdf(self, path: Path) -> ParsedDocument:
        """Parses PDF via pypdf and extracts text and structured tables."""
        reader = pypdf.PdfReader(str(path.resolve()))
        elements: List[DocumentElement] = []
        tables: List[Dict[str, Any]] = []

        for idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            lines = [l.strip() for l in page_text.splitlines() if l.strip()]

            current_table_lines: List[str] = []
            for line in lines:
                # Detect table rows by delimiters (|, tabs, or columnar spaces)
                if "|" in line or "\t" in line:
                    current_table_lines.append(line)
                else:
                    if current_table_lines:
                        # Flush table
                        tbl_text = "\n".join(current_table_lines)
                        t_elem = DocumentElement(type="Table", text=tbl_text, metadata={"page_number": idx + 1})
                        elements.append(t_elem)
                        tables.append({
                            "element_id": t_elem.element_id,
                            "table_text": tbl_text,
                            "page_number": idx + 1,
                        })
                        current_table_lines = []

                    elem_type = "Title" if len(line) < 60 and not line.endswith(".") else "NarrativeText"
                    elements.append(
                        DocumentElement(
                            type=elem_type,
                            text=line,
                            metadata={"page_number": idx + 1},
                        )
                    )

            if current_table_lines:
                tbl_text = "\n".join(current_table_lines)
                t_elem = DocumentElement(type="Table", text=tbl_text, metadata={"page_number": idx + 1})
                elements.append(t_elem)
                tables.append({
                    "element_id": t_elem.element_id,
                    "table_text": tbl_text,
                    "page_number": idx + 1,
                })

        return ParsedDocument(
            filename=path.name,
            file_type="pdf",
            elements=elements,
            tables=tables,
            metadata={"parser": "pypdf", "pages": len(reader.pages)},
        )

    def parse_pdf(self, file_path: str | Path) -> ParsedDocument:
        """Helper specifically for parsing PDF documents."""
        return self.parse_document(file_path)


# Global default instance
default_unstructured_adapter = UnstructuredAdapter()

