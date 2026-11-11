"""Tests for Document Extensions (1.13, 1.14, 1.15, 1.16, 1.17, 1.18, 1.20)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from cognitive.perception.document.batch_processor import BatchDocumentProcessor
from cognitive.perception.document.chart_extractor import ChartExtractor
from cognitive.perception.document.form_extractor import FormFieldExtractor
from cognitive.perception.document.formula_recognizer import FormulaRecognizer
from cognitive.perception.document.unstructured_adapter import (
    DocumentElement,
    ParsedDocument,
    UnstructuredAdapter,
)
from cognitive.perception.vision.vlm_client import VLMAnalysisResult, VLMClient


@pytest.mark.asyncio
async def test_document_extensions_and_batch(tmp_path: Path) -> None:
    adapter = UnstructuredAdapter(languages=["eng", "jpn", "ara", "hin"])

    # 1.13 Multi-language detection (Japanese, Arabic, Hindi)
    jp_doc = ParsedDocument(filename="jp.txt", file_type="txt", elements=[DocumentElement(text="日本語のテスト文書")])
    assert adapter.detect_document_language(jp_doc)["language"] == "ja"
    ar_doc = ParsedDocument(filename="ar.txt", file_type="txt", elements=[DocumentElement(text="مرحبا بالعالم")])
    assert adapter.detect_document_language(ar_doc)["language"] == "ar"
    hi_doc = ParsedDocument(filename="hi.txt", file_type="txt", elements=[DocumentElement(text="नमस्ते दुनिया")])
    assert adapter.detect_document_language(hi_doc)["language"] == "hi"

    # 1.14 Table JSON extraction (3x4 table)
    tbl_doc = ParsedDocument(
        filename="report.pdf",
        file_type="pdf",
        elements=[DocumentElement(type="Title", text="Quarterly Metrics"), DocumentElement(type="NarrativeText", text="Summary paragraph.")],
        tables=[{"element_id": "t1", "page_number": 1, "table_text": "Qtr | Rev | Cost | Net\nQ1 | 100 | 40 | 60\nQ2 | 150 | 50 | 100"}],
    )
    tables_json = adapter.extract_tables_json(tbl_doc)
    assert tables_json[0]["num_rows"] == 3
    assert tables_json[0]["num_cols"] == 4
    assert tables_json[0]["records"][1]["Net"] == "100"

    # 1.16 Layout hierarchy
    layout = adapter.extract_layout_hierarchy(tbl_doc)
    assert layout["section_count"] == 1
    assert layout["sections"][0]["heading"] == "Quarterly Metrics"

    # 1.15 Form extractor
    form = FormFieldExtractor().extract_from_text("Full Name: Jane Doe\nTax Year: 2026\nTotal Income: $95,000\n[x] W-2 Attached")
    assert form.fields["Full Name"] == "Jane Doe"
    assert form.fields["W-2 Attached"] == "true"

    # 1.17 Formula & 1.18 Chart extractors
    img = Image.new("RGB", (64, 64), color=(255, 255, 255))
    mock_vlm = MagicMock(spec=VLMClient)
    mock_vlm.analyze_image.return_value = VLMAnalysisResult(description="```latex\nE = mc^2\n```")
    assert FormulaRecognizer(mock_vlm).recognize(img).latex == "E = mc^2"

    mock_vlm.analyze_image.return_value = VLMAnalysisResult(
        description='{"chart_type": "bar", "title": "Sales", "points": [{"label": "Jan", "value": 42}, {"label": "Feb", "value": 84}]}'
    )
    chart = ChartExtractor(mock_vlm).extract(img)
    assert len(chart.points) == 2
    assert chart.points[1].value == 84.0

    # 1.20 Parallel batch of 10 documents
    files = []
    for i in range(10):
        f = tmp_path / f"doc_{i}.txt"
        f.write_text(f"Document {i} body content.", encoding="utf-8")
        files.append(f)
    batch_res = await BatchDocumentProcessor(adapter=adapter).process_batch(files)
    assert batch_res.succeeded == 10
    assert batch_res.failed == 0

