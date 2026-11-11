"""Form Field Key-Value Pair Extractor (L1 Feature 1.15)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from cognitive.perception.document.unstructured_adapter import UnstructuredAdapter


@dataclass
class ExtractedFormField:
    """Single key-value field parsed from a structured form."""

    key: str
    value: str
    page_number: int = 1
    field_type: str = "text"  # text, date, signature, checkbox, currency


@dataclass
class FormExtractionResult:
    """Structured key-value extraction result across an entire form document."""

    filename: str
    fields: Dict[str, str] = field(default_factory=dict)
    items: List[ExtractedFormField] = field(default_factory=list)


_KV_PATTERN = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 _/\-().]{1,48})\s*[:=]\s*(.+?)\s*$")
_CHECKBOX_PATTERN = re.compile(r"^\s*\[([xX ])\]\s*(.+?)\s*$")


def _infer_field_type(key: str, value: str) -> str:
    lk = key.lower()
    if "date" in lk or re.match(r"^\d{4}-\d{2}-\d{2}$|^\d{2}/\d{2}/\d{4}$", value):
        return "date"
    if "sign" in lk:
        return "signature"
    if "$" in value or any(tok in lk for tok in ("income", "tax", "amount", "total")):
        return "currency"
    return "text"


class FormFieldExtractor:
    """Extracts key-value pairs and checkboxes from PDF/text forms."""

    def __init__(self, doc_adapter: Optional[UnstructuredAdapter] = None) -> None:
        self.doc_adapter = doc_adapter or UnstructuredAdapter()

    def extract_from_text(self, text: str, filename: str = "inline.txt") -> FormExtractionResult:
        fields: Dict[str, str] = {}
        items: List[ExtractedFormField] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            cb = _CHECKBOX_PATTERN.match(line)
            if cb:
                checked = "true" if cb.group(1).lower() == "x" else "false"
                key = cb.group(2).strip()
                fields[key] = checked
                items.append(ExtractedFormField(key=key, value=checked, field_type="checkbox"))
                continue
            kv = _KV_PATTERN.match(line)
            if kv:
                key, val = kv.group(1).strip(), kv.group(2).strip()
                fields[key] = val
                items.append(
                    ExtractedFormField(
                        key=key,
                        value=val,
                        field_type=_infer_field_type(key, val),
                    )
                )
        return FormExtractionResult(filename=filename, fields=fields, items=items)

    def extract_from_file(self, file_path: str | Path) -> FormExtractionResult:
        parsed = self.doc_adapter.parse_document(file_path)
        res = self.extract_from_text(parsed.full_text, filename=parsed.filename)
        return res

