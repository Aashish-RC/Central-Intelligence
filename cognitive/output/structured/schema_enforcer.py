"""Schema-Enforced JSON Validator & Structured Form Filler (L6 Features 6.21, 6.23, 6.24)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List


class SchemaValidationError(ValueError):
    """Raised when structured output violates required API schema constraints."""


class SchemaEnforcer:
    """Validates and normalizes JSON/dict payloads against JSON-Schema specs."""

    _TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "object": dict,
        "array": list,
    }

    def validate(self, payload: str | Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Parse (even fenced Markdown JSON) and validate against `schema`."""
        if isinstance(payload, str):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", payload.strip(), flags=re.IGNORECASE)
            data = json.loads(cleaned)
        else:
            data = dict(payload)

        if not isinstance(data, dict):
            raise SchemaValidationError("Expected top-level JSON object")

        props: Dict[str, Any] = schema.get("properties", {})
        required: List[str] = list(schema.get("required", []))

        # Populate defaults before required validation
        for key, spec in props.items():
            if key not in data and "default" in spec:
                data[key] = spec["default"]

        for req_key in required:
            if req_key not in data or data[req_key] is None:
                raise SchemaValidationError(f"Missing required schema property '{req_key}'")

        for key, spec in props.items():
            if key not in data:
                continue
            expected_type = spec.get("type")
            if expected_type and expected_type in self._TYPE_MAP:
                py_t = self._TYPE_MAP[expected_type]
                # Avoid bool passing int check in Python
                if expected_type in ("integer", "number") and isinstance(data[key], bool):
                    raise SchemaValidationError(f"Property '{key}' expected {expected_type}, got bool")
                if not isinstance(data[key], py_t):
                    raise SchemaValidationError(
                        f"Property '{key}' expected {expected_type}, got {type(data[key]).__name__}"
                    )
            if "enum" in spec and data[key] not in spec["enum"]:
                raise SchemaValidationError(f"Property '{key}'={data[key]!r} not in allowed enum {spec['enum']}")
        return data


@dataclass
class FormFillResult:
    """Result of auto-filling a structured form from user/extracted entities."""

    filled_fields: Dict[str, Any]
    missing_required: List[str] = field(default_factory=list)
    complete: bool = True


class StructuredFormFiller:
    """Maps extracted key-value entities and natural text into form definitions."""

    def fill_form(
        self,
        form_schema: List[Dict[str, Any]],
        context_entities: Dict[str, Any],
    ) -> FormFillResult:
        """Populate form fields via exact key or alias matching and report gaps."""
        lowered = {k.lower().replace(" ", "_"): v for k, v in context_entities.items()}
        filled: Dict[str, Any] = {}
        missing: List[str] = []

        for field_def in form_schema:
            name = str(field_def["name"])
            aliases = [name.lower()] + [str(a).lower() for a in field_def.get("aliases", [])]
            matched_val = None
            for alias in aliases:
                norm = alias.replace(" ", "_")
                if norm in lowered:
                    matched_val = lowered[norm]
                    break
            if matched_val is not None:
                filled[name] = matched_val
            elif "default" in field_def:
                filled[name] = field_def["default"]
            elif field_def.get("required", False):
                missing.append(name)

        return FormFillResult(
            filled_fields=filled,
            missing_required=missing,
            complete=len(missing) == 0,
        )

