"""
Unit tests for Unstructured Document Parsing Adapter (Layer 1: Perception, Task 1.5).
"""

from pathlib import Path
import pytest
from cognitive.perception.document.unstructured_adapter import (
    DocumentElement,
    ParsedDocument,
    UnstructuredAdapter,
)


def create_sample_pdf(file_path: Path) -> Path:
    """Generates a valid minimal PDF containing titles, narrative text, and a markdown table."""
    pdf_bytes = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 260 >> stream
BT
/F1 12 Tf
72 720 Td (Annual Intelligence Operations Summary) Tj
0 -30 Td (This report covers multi-modal perception benchmarks.) Tj
0 -30 Td (| Metric | Value | Status |) Tj
0 -20 Td (| Latency | 50ms | Optimal |) Tj
0 -20 Td (| Accuracy | 99% | Passed |) Tj
ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000555 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
634
%%EOF"""
    file_path.write_bytes(pdf_bytes)
    return file_path


def test_parse_pdf_to_structured_json(tmp_path: Path):
    """
    Acceptance: Can parse a PDF and return structured JSON with tables and text.
    """
    adapter = UnstructuredAdapter()
    sample_pdf = create_sample_pdf(tmp_path / "quarterly_brief.pdf")

    parsed = adapter.parse_pdf(sample_pdf)

    assert isinstance(parsed, ParsedDocument)
    assert parsed.filename == "quarterly_brief.pdf"
    assert parsed.file_type == "pdf"

    # Verify structured JSON output
    data = parsed.to_dict()
    assert isinstance(data, dict)
    assert "elements" in data
    assert "tables" in data
    assert "full_text" in data
    assert data["total_elements"] > 0

    # Verify text extraction
    assert "Annual Intelligence Operations Summary" in parsed.full_text
    assert "This report covers multi-modal perception benchmarks." in parsed.full_text

    # Verify table extraction
    assert len(parsed.tables) >= 1
    table_text = parsed.tables[0]["table_text"]
    assert "Metric" in table_text
    assert "Latency" in table_text
    assert "Optimal" in table_text


def test_parse_text_document(tmp_path: Path):
    """Verify fallback handling for non-PDF documents (e.g. TXT/MD)."""
    adapter = UnstructuredAdapter()
    txt_file = tmp_path / "system_spec.txt"
    txt_file.write_text("Central Intelligence Platform Architecture Specification\nVersion 2.0")

    parsed = adapter.parse_document(txt_file)
    assert parsed.file_type == "txt"
    assert "Version 2.0" in parsed.full_text
    json_str = parsed.to_json()
    assert "system_spec.txt" in json_str


def test_parse_missing_file_raises_error():
    """Verify appropriate error handling for nonexistent file."""
    adapter = UnstructuredAdapter()
    with pytest.raises(FileNotFoundError):
        adapter.parse_document("nonexistent_report.pdf")

