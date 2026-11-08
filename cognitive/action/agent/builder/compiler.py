"""Manifest Compiler: Compiles Visual Graph/Node Topologies (Langflow / React Flow) into AgentManifest."""

from typing import Any, Dict, List, Optional
from agent.core.manifest import (
    AgentManifest,
    AgentMetadata,
    RuntimeConfig,
    MemoryConfig,
    MemoryTiersConfig,
    SemanticSearchConfig,
    GuardrailConfig,
    SandboxConfig,
    ToolDefinition,
    SubagentConfig,
)
from .schema_validator import SchemaValidator
from agent.core.exceptions import ManifestValidationError


class ManifestCompiler:
    """Compiles visual canvas / workflow graph structures into a validated AgentManifest."""

    @classmethod
    def compile_graph(cls, graph_data: Dict[str, Any]) -> AgentManifest:
        """Compile a graph containing 'nodes' and 'edges' into an AgentManifest.

        Supports standard Langflow / React-Flow node configurations.
        """
        nodes: List[Dict[str, Any]] = graph_data.get("nodes", [])
        if not nodes:
            raise ManifestValidationError("Graph contains no nodes to compile")

        agent_id = "compiled-agent"
        metadata = AgentMetadata(name="Compiled Agent", description="Generated from visual canvas")
        runtime = RuntimeConfig()
        memory = MemoryConfig()
        guardrails = GuardrailConfig()
        sandbox = SandboxConfig()
        tools: List[ToolDefinition] = []
        subagents: List[SubagentConfig] = []

        for node in nodes:
            node_type = node.get("type", "").lower()
            data = node.get("data", {})

            # 1. Agent Root / Identity Node
            if node_type in ("agent", "agent_root", "agentnode"):
                agent_id = data.get("agent_id") or data.get("id") or agent_id
                metadata.name = data.get("name", metadata.name)
                metadata.description = data.get("description", metadata.description)
                metadata.tags = data.get("tags", metadata.tags)
                metadata.author = data.get("author", metadata.author)

            # 2. Runtime / LLM Node
            elif node_type in ("model", "llm", "runtime", "modelnode"):
                if "engine" in data:
                    runtime.engine = data["engine"]
                if "model" in data:
                    runtime.model = data["model"]
                if "temperature" in data:
                    runtime.temperature = float(data["temperature"])
                if "max_steps" in data:
                    runtime.max_steps = int(data["max_steps"])
                if "system_prompt" in data:
                    runtime.system_prompt = data["system_prompt"]

            # 3. Memory Node
            elif node_type in ("memory", "memorynode", "fused_memory"):
                memory.enabled = data.get("enabled", True)
                memory.shared_namespace = data.get("shared_namespace", memory.shared_namespace)
                tiers_data = data.get("tiers", {})
                working_mem = tiers_data.get("working_memory", True)
                user_facts = tiers_data.get("user_facts", True)
                semantic_data = tiers_data.get("semantic_search", {})

                semantic_cfg = None
                if semantic_data:
                    semantic_cfg = SemanticSearchConfig(
                        collection=semantic_data.get("collection", "default_kb"),
                        top_k=semantic_data.get("top_k", 5),
                        threshold=semantic_data.get("threshold", 0.7),
                    )

                memory.tiers = MemoryTiersConfig(
                    working_memory=working_mem,
                    user_facts=user_facts,
                    semantic_search=semantic_cfg or SemanticSearchConfig(),
                )

            # 4. Tool Node
            elif node_type in ("tool", "toolnode", "action"):
                tool = ToolDefinition(
                    name=data.get("name", f"tool_{len(tools)+1}"),
                    type=data.get("tool_type", data.get("type", "builtin")),
                    endpoint=data.get("endpoint"),
                    command=data.get("command"),
                    description=data.get("description"),
                    parameters=data.get("parameters", {}),
                )
                tools.append(tool)

            # 5. Guardrail Node
            elif node_type in ("guardrail", "guardrails", "guardrailnode"):
                guardrails.provider = data.get("provider", "parlant")
                guardrails.ruleset_id = data.get("ruleset_id")
                guardrails.blocked_keywords = data.get("blocked_keywords", [])
                guardrails.guidelines = data.get("guidelines", [])

            # 6. Sandbox Node
            elif node_type in ("sandbox", "sandboxnode", "e2b"):
                sandbox.required = data.get("required", True)
                sandbox.provider = data.get("provider", "local")
                sandbox.template = data.get("template", "python-3.11-data-science")
                sandbox.timeout_seconds = int(data.get("timeout_seconds", 60))

            # 7. Subagent Node
            elif node_type in ("subagent", "subagentnode", "child_agent"):
                subagent = SubagentConfig(
                    subagent_id=data.get("subagent_id", f"subagent_{len(subagents)+1}"),
                    role=data.get("role", "Specialized Assistant"),
                    manifest_path=data.get("manifest_path"),
                    inline_manifest=data.get("inline_manifest"),
                )
                subagents.append(subagent)

        manifest = AgentManifest(
            agent_id=agent_id,
            metadata=metadata,
            runtime=runtime,
            memory=memory,
            guardrails=guardrails,
            sandbox=sandbox,
            tools=tools,
            subagents=subagents,
        )

        # Validate through SchemaValidator
        return SchemaValidator.assert_valid(manifest.to_dict())
