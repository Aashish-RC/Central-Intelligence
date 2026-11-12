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

from cognitive.perception.translation.core.detector import LocaleDetector
from control.safety.production_guard import (
    fail_closed_in_production,
    require_live_adapter,
)

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

    def __init__(
        self,
        strategy: str = "auto",
        languages: Optional[List[str]] = None,
        _defer_prod_check: bool = False,
    ) -> None:
        self.strategy = strategy
        self.languages = list(languages) if languages else ["eng"]
        self._locale_detector = LocaleDetector()
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("unstructured")
        )

    @staticmethod
    def _parse_table_rows(table_text: str) -> List[List[str]]:
        """Parse pipe- or tab-delimited table text into normalized rows and cells."""
        rows: List[List[str]] = []
        for raw_line in table_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if "|" in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                # Skip markdown separator rows like |---|---|
                if all(set(c) <= set("-: ") for c in cells):
                    continue
                rows.append(cells)
            elif "\t" in line:
                rows.append([c.strip() for c in line.split("\t")])
        return rows

    def detect_document_language(self, doc: ParsedDocument) -> Dict[str, Any]:
        """Detect dominant language and Unicode script across parsed document elements (1.13)."""
        sample = doc.full_text[:2000].strip()
        if not sample:
            return {"language": "und", "script": "unknown", "confidence": 0.0}
        res = self._locale_detector.detect(sample)
        return {
            "language": res.language,
            "script": res.script,
            "confidence": res.confidence,
        }

    def extract_tables_json(self, doc: ParsedDocument) -> List[Dict[str, Any]]:
        """Convert parsed document tables into structured row/column JSON dicts (1.14)."""
        structured: List[Dict[str, Any]] = []
        for idx, tbl in enumerate(doc.tables):
            rows = self._parse_table_rows(tbl.get("table_text", ""))
            headers = rows[0] if rows else []
            data_rows = rows[1:] if len(rows) > 1 else []
            structured.append({
                "table_index": idx,
                "element_id": tbl.get("element_id"),
                "page_number": tbl.get("page_number", 1),
                "headers": headers,
                "rows": rows,
                "records": [
                    {headers[i]: (r[i] if i < len(r) else "") for i in range(len(headers))}
                    for r in data_rows
                ] if headers else [],
                "num_rows": len(rows),
                "num_cols": max((len(r) for r in rows), default=0),
            })
        return structured

    def extract_layout_hierarchy(self, doc: ParsedDocument) -> Dict[str, Any]:
        """Order elements into reading order and nested sections by heading/title (1.16)."""
        sections: List[Dict[str, Any]] = []
        current: Dict[str, Any] = {"heading": None, "level": 0, "elements": []}
        for order_idx, elem in enumerate(doc.elements):
            if elem.type in ("Title", "Header"):
                if current["heading"] or current["elements"]:
                    sections.append(current)
                current = {
                    "heading": elem.text,
                    "level": 1,
                    "reading_order": order_idx,
                    "elements": [],
                }
            else:
                current["elements"].append({
                    "reading_order": order_idx,
                    "type": elem.type,
                    "text": elem.text,
                    "page_number": elem.metadata.get("page_number", 1),
                })
        if current["heading"] or current["elements"]:
            sections.append(current)
        return {
            "filename": doc.filename,
            "section_count": len(sections),
            "sections": sections,
        }

    def parse_document(self, file_path: str | Path) -> ParsedDocument:
        """
        Parses document at file_path (PDF, DOCX, PPTX, XLSX, TXT) into structured JSON.
        """
        self.adapter_mode = require_live_adapter("unstructured")
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

        # Fallback for PDF documents using pypdf (or pure-Python PDF stream parser)
        if ext == "pdf":
            if _PYPDF_AVAILABLE:
                return self._parse_pdf_pypdf(path)
            return self._parse_pdf_text_operators(path)

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

    def _extract_elements_from_lines(
        self,
        lines: List[str],
        page_number: int,
    ) -> tuple[List[DocumentElement], List[Dict[str, Any]]]:
        """Group extracted page lines into structured elements and tables."""
        elements: List[DocumentElement] = []
        tables: List[Dict[str, Any]] = []
        current_table_lines: List[str] = []

        def flush_table() -> None:
            if not current_table_lines:
                return
            tbl_text = "\n".join(current_table_lines)
            t_elem = DocumentElement(type="Table", text=tbl_text, metadata={"page_number": page_number})
            elements.append(t_elem)
            tables.append({
                "element_id": t_elem.element_id,
                "table_text": tbl_text,
                "page_number": page_number,
            })
            current_table_lines.clear()

        for line in lines:
            if "|" in line or "\t" in line:
                current_table_lines.append(line)
            else:
                flush_table()
                elem_type = "Title" if len(line) < 60 and not line.endswith(".") else "NarrativeText"
                elements.append(
                    DocumentElement(
                        type=elem_type,
                        text=line,
                        metadata={"page_number": page_number},
                    )
                )

        flush_table()
        return elements, tables

    def _parse_pdf_pypdf(self, path: Path) -> ParsedDocument:
        """Parses PDF via pypdf and extracts text and structured tables."""
        reader = pypdf.PdfReader(str(path.resolve()))
        elements: List[DocumentElement] = []
        tables: List[Dict[str, Any]] = []

        for idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            lines = [line.strip() for line in page_text.splitlines() if line.strip()]
            page_elems, page_tables = self._extract_elements_from_lines(lines, page_number=idx + 1)
            elements.extend(page_elems)
            tables.extend(page_tables)

        return ParsedDocument(
            filename=path.name,
            file_type="pdf",
            elements=elements,
            tables=tables,
            metadata={"parser": "pypdf", "pages": len(reader.pages)},
        )

    def _parse_pdf_text_operators(self, path: Path) -> ParsedDocument:
        """Pure-Python fallback extracting PDF Tj/TJ text operators and tables when pypdf is unavailable."""
        import re

        raw = path.read_bytes().decode("latin-1", errors="ignore")
        lines = [
            match.group(1).replace(r"\(", "(").replace(r"\)", ")").strip()
            for match in re.finditer(r"\(([^()]*)\)\s*Tj", raw)
        ]
        lines = [line for line in lines if line]
        elements, tables = self._extract_elements_from_lines(lines, page_number=1)
        return ParsedDocument(
            filename=path.name,
            file_type="pdf",
            elements=elements,
            tables=tables,
            metadata={"parser": "pdf_stream_fallback", "pages": 1},
        )

    def parse_pdf(self, file_path: str | Path) -> ParsedDocument:
        """Helper specifically for parsing PDF documents."""
        return self.parse_document(file_path)


# Global default instance
default_unstructured_adapter = UnstructuredAdapter()

