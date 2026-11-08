"""JSONSchema & Semantic Validation Engine for AgentManifests."""

from typing import Any, Dict, List, Tuple
from pydantic import ValidationError
import jsonschema

from agent.core.manifest import AgentManifest
from agent.core.exceptions import ManifestValidationError


# Canonical JSON Schema for AgentManifest
AGENT_MANIFEST_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AgentManifest",
    "type": "object",
    "required": ["agent_id", "metadata"],
    "properties": {
        "$schema": {"type": "string"},
        "agent_id": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9_-]+$",
            "minLength": 1,
            "maxLength": 128
        },
        "version": {"type": "string"},
        "metadata": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "description": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "author": {"type": "string"}
            }
        },
        "runtime": {
            "type": "object",
            "properties": {
                "engine": {"type": "string"},
                "model": {"type": "string"},
                "temperature": {"type": "number", "minimum": 0.0, "maximum": 2.0},
                "max_steps": {"type": "integer", "minimum": 1, "maximum": 200},
                "system_prompt": {"type": "string"}
            }
        },
        "memory": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "shared_namespace": {"type": "string"},
                "tiers": {
                    "type": "object",
                    "properties": {
                        "working_memory": {"type": "boolean"},
                        "user_facts": {"type": "boolean"},
                        "semantic_search": {
                            "type": "object",
                            "properties": {
                                "collection": {"type": "string"},
                                "top_k": {"type": "integer", "minimum": 1}
                            }
                        }
                    }
                }
            }
        },
        "guardrails": {
            "type": "object",
            "properties": {
                "provider": {"type": "string"},
                "ruleset_id": {"type": "string"},
                "blocked_keywords": {"type": "array", "items": {"type": "string"}},
                "guidelines": {"type": "array", "items": {"type": "string"}}
            }
        },
        "sandbox": {
            "type": "object",
            "properties": {
                "required": {"type": "boolean"},
                "provider": {"type": "string"},
                "template": {"type": "string"},
                "timeout_seconds": {"type": "integer", "minimum": 1}
            }
        },
        "tools": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "endpoint": {"type": "string"},
                    "command": {"type": "string"},
                    "description": {"type": "string"},
                    "parameters": {"type": "object"}
                }
            }
        },
        "subagents": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["subagent_id", "role"],
                "properties": {
                    "subagent_id": {"type": "string"},
                    "role": {"type": "string"},
                    "manifest_path": {"type": "string"},
                    "inline_manifest": {"type": "object"}
                }
            }
        }
    }
}


class SchemaValidator:
    """Validator performing dual-tier validation: Structural JSONSchema + Semantic Pydantic Rules."""

    @classmethod
    def validate_dict(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate raw dictionary against JSONSchema and Pydantic constraints.

        Returns (is_valid, list_of_errors).
        """
        errors: List[str] = []

        # 1. Structural JSONSchema validation
        try:
            validator = jsonschema.Draft202012Validator(AGENT_MANIFEST_JSON_SCHEMA)
            for err in validator.iter_errors(data):
                field_path = ".".join(str(p) for p in err.absolute_path)
                msg = f"Schema error at '{field_path or 'root'}': {err.message}"
                errors.append(msg)
        except Exception as e:
            errors.append(f"JSONSchema validation crashed: {str(e)}")

        # 2. Semantic Pydantic validation
        try:
            manifest = AgentManifest.from_dict(data)
            # Custom semantic checks
            # a. Check tool duplicate names
            tool_names = [t.name for t in manifest.tools]
            if len(tool_names) != len(set(tool_names)):
                errors.append("Duplicate tool names detected in tools list")

            # b. Check subagent cycles or self-reference
            for sub in manifest.subagents:
                if sub.subagent_id == manifest.agent_id:
                    errors.append(f"Self-referential subagent detected: '{sub.subagent_id}'")

        except ValidationError as ve:
            for error_dict in ve.errors():
                loc = ".".join(str(l) for l in error_dict.get("loc", []))
                errors.append(f"Validation error at '{loc}': {error_dict.get('msg')}")
        except ManifestValidationError as mve:
            errors.append(str(mve))

        is_valid = len(errors) == 0
        return is_valid, errors

    @classmethod
    def assert_valid(cls, data: Dict[str, Any]) -> AgentManifest:
        """Validate and return parsed AgentManifest, raising ManifestValidationError if invalid."""
        is_valid, errors = cls.validate_dict(data)
        if not is_valid:
            raise ManifestValidationError(
                f"Manifest validation failed with {len(errors)} error(s): " + "; ".join(errors),
                details={"errors": errors}
            )
        return AgentManifest.from_dict(data)
