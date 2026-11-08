"""Test suite for AgentManifest schema validation, rejection, and serialization."""

import pytest
from agent.core.manifest import AgentManifest, AgentMetadata, RuntimeConfig
from agent.builder.schema_validator import SchemaValidator
from agent.builder.templates import CoderAgentBlueprint, ResearcherAgentBlueprint, SupportAgentBlueprint
from agent.core.exceptions import ManifestValidationError


def test_valid_manifest_creation():
    manifest = CoderAgentBlueprint.create()
    assert manifest.agent_id == "code-auditor-agent"
    assert manifest.runtime.engine == "agno"
    assert manifest.sandbox.required is True
    assert len(manifest.tools) >= 2


def test_manifest_serialization_roundtrip():
    manifest = ResearcherAgentBlueprint.create()
    json_str = manifest.to_json()
    reconstructed = AgentManifest.from_json(json_str)

    assert reconstructed.agent_id == manifest.agent_id
    assert reconstructed.runtime.model == manifest.runtime.model
    assert reconstructed.memory.shared_namespace == manifest.memory.shared_namespace

    yaml_str = manifest.to_yaml()
    reconstructed_yaml = AgentManifest.from_yaml(yaml_str)
    assert reconstructed_yaml.agent_id == manifest.agent_id


def test_schema_validator_accepts_valid():
    manifest = SupportAgentBlueprint.create()
    is_valid, errors = SchemaValidator.validate_dict(manifest.to_dict())
    assert is_valid is True
    assert len(errors) == 0


def test_schema_validator_rejects_missing_metadata():
    invalid_data = {
        "agent_id": "test-agent",
        # Missing metadata
    }
    is_valid, errors = SchemaValidator.validate_dict(invalid_data)
    assert is_valid is False
    assert any("metadata" in e for e in errors)


def test_schema_validator_rejects_invalid_id_characters():
    invalid_data = {
        "agent_id": "invalid ID with spaces!!",
        "metadata": {"name": "Bad Agent"},
    }
    is_valid, errors = SchemaValidator.validate_dict(invalid_data)
    assert is_valid is False


def test_schema_validator_rejects_duplicate_tools():
    data = {
        "agent_id": "duplicate-tools-agent",
        "metadata": {"name": "Dup Agent"},
        "tools": [
            {"name": "tool_a", "type": "builtin"},
            {"name": "tool_a", "type": "builtin"},
        ]
    }
    is_valid, errors = SchemaValidator.validate_dict(data)
    assert is_valid is False
    assert any("Duplicate tool" in e for e in errors)


def test_schema_validator_rejects_self_referential_subagent():
    data = {
        "agent_id": "loop-agent",
        "metadata": {"name": "Loop Agent"},
        "subagents": [
            {"subagent_id": "loop-agent", "role": "Self"}
        ]
    }
    is_valid, errors = SchemaValidator.validate_dict(data)
    assert is_valid is False
    assert any("Self-referential" in e for e in errors)
