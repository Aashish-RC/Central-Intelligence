"""Universal Contract: AgentManifest Pydantic v2 Schema.

Decouples the Builder Engine from the Executor Engine via an explicit,
declarative contract.
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
import yaml

from .exceptions import ManifestValidationError


class AgentMetadata(BaseModel):
    name: str = Field(..., min_length=1, description="Human-readable name of the agent")
    description: str = Field(default="", description="Detailed summary of agent purpose and capabilities")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    author: Optional[str] = Field(default=None, description="Creator identity or organization")


class RuntimeConfig(BaseModel):
    engine: str = Field(default="agno", description="Agent runtime engine (e.g. agno, hermes, custom)")
    model: str = Field(default="gemini-2.5-flash", description="Underlying LLM model identifier")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="Sampling temperature")
    max_steps: int = Field(default=25, ge=1, le=200, description="Maximum execution reasoning steps")
    system_prompt: Optional[str] = Field(default=None, description="Custom system instruction preamble")


class SemanticSearchConfig(BaseModel):
    collection: str = Field(default="default_kb", description="Vector collection / index name")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of semantic chunks to recall")
    threshold: Optional[float] = Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity score")


class MemoryTiersConfig(BaseModel):
    working_memory: bool = Field(default=True, description="Enable fast session scratchpad & WAL")
    user_facts: bool = Field(default=True, description="Enable structured entity & rule store")
    semantic_search: Optional[SemanticSearchConfig] = Field(
        default_factory=SemanticSearchConfig,
        description="Semantic vector memory configuration"
    )


class MemoryConfig(BaseModel):
    enabled: bool = Field(default=True, description="Master switch for memory integration")
    shared_namespace: str = Field(default="default", min_length=1, description="Tenant/User isolation namespace")
    tiers: MemoryTiersConfig = Field(default_factory=MemoryTiersConfig)


class GuardrailConfig(BaseModel):
    provider: str = Field(default="parlant", description="Guardrails provider ('parlant' or 'local')")
    ruleset_id: Optional[str] = Field(default=None, description="Identifier for enterprise compliance ruleset")
    blocked_keywords: List[str] = Field(default_factory=list, description="Explicit blacklisted patterns")
    guidelines: List[str] = Field(default_factory=list, description="Behavioral guidance rules")


class SandboxConfig(BaseModel):
    required: bool = Field(default=False, description="Whether isolated execution environment is required")
    provider: str = Field(default="local", description="Sandbox backend ('e2b' or 'local')")
    template: Optional[str] = Field(default="python-3.11-data-science", description="Pre-baked VM template")
    timeout_seconds: int = Field(default=60, ge=1, le=600, description="Hard timeout for commands")


class ToolDefinition(BaseModel):
    name: str = Field(..., min_length=1, description="Unique identifier for the tool")
    type: str = Field(default="builtin", description="Tool category: api, sandbox_command, python_function, builtin")
    endpoint: Optional[str] = Field(default=None, description="API endpoint if type is api")
    command: Optional[str] = Field(default=None, description="Shell command template if type is sandbox_command")
    description: Optional[str] = Field(default=None, description="Description given to the LLM for function calling")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="JSONSchema parameter definitions")


class SubagentConfig(BaseModel):
    subagent_id: str = Field(..., min_length=1, description="Identifier of the child agent")
    role: str = Field(..., min_length=1, description="Delegated specialized role")
    manifest_path: Optional[str] = Field(default=None, description="Path to subagent manifest file")
    inline_manifest: Optional[Dict[str, Any]] = Field(default=None, description="Directly embedded subagent manifest")


class AgentManifest(BaseModel):
    """Universal Declarative Specification for Autonomous Agents."""

    schema_version: Optional[str] = Field(
        default="https://json-schema.org/draft/2020-12/schema",
        alias="$schema"
    )
    agent_id: str = Field(..., min_length=1, max_length=128, description="Unique slug for the agent")
    version: str = Field(default="1.0.0", description="Semantic version string")
    metadata: AgentMetadata = Field(..., description="Agent descriptive metadata")
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    guardrails: GuardrailConfig = Field(default_factory=GuardrailConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    tools: List[ToolDefinition] = Field(default_factory=list)
    subagents: List[SubagentConfig] = Field(default_factory=list)

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, v: str) -> str:
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"agent_id '{v}' must be alphanumeric with optional dashes and underscores")
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to Python dictionary."""
        return self.model_dump(by_alias=True, exclude_none=True)

    def to_json(self, indent: int = 2) -> str:
        """Serialize manifest to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_yaml(self) -> str:
        """Serialize manifest to YAML string."""
        return yaml.dump(self.to_dict(), sort_keys=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentManifest:
        """Parse and validate manifest from Python dictionary."""
        try:
            return cls.model_validate(data)
        except Exception as err:
            raise ManifestValidationError(f"Invalid AgentManifest schema: {err}", details={"error": str(err)})

    @classmethod
    def from_json(cls, json_str: str) -> AgentManifest:
        """Parse and validate manifest from JSON string."""
        try:
            data = json.loads(json_str)
        except Exception as err:
            raise ManifestValidationError(f"Invalid JSON in manifest: {err}")
        return cls.from_dict(data)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> AgentManifest:
        """Parse and validate manifest from YAML string."""
        try:
            data = yaml.safe_load(yaml_str)
        except Exception as err:
            raise ManifestValidationError(f"Invalid YAML in manifest: {err}")
        return cls.from_dict(data)
