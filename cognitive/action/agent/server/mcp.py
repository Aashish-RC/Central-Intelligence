"""Model Context Protocol (MCP) Server for IDE Ingestion."""

import json
from typing import Any, Dict, List
from agent.core.manifest import AgentManifest
from agent.builder.schema_validator import SchemaValidator
from agent.builder.templates import CoderAgentBlueprint, ResearcherAgentBlueprint
from agent.executor.runner import AgentRunner
from agent.memory.manager import default_memory_manager


class AgentMCPServer:
    """Provides standard MCP JSON-RPC tool endpoints for AI IDEs."""

    def __init__(self):
        self._runners: Dict[str, AgentRunner] = {
            "code-auditor-agent": AgentRunner(manifest=CoderAgentBlueprint.create()),
            "deep-researcher-agent": AgentRunner(manifest=ResearcherAgentBlueprint.create()),
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return list of MCP tools exposed to IDE."""
        return [
            {
                "name": "build_agent",
                "description": "Validates and registers an AgentManifest in the control plane.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "manifest_json": {"type": "string", "description": "JSON string of AgentManifest"}
                    },
                    "required": ["manifest_json"]
                }
            },
            {
                "name": "execute_agent",
                "description": "Runs a prompt through an active agent and returns findings.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string"},
                        "prompt": {"type": "string"},
                        "session_id": {"type": "string"}
                    },
                    "required": ["agent_id", "prompt"]
                }
            },
            {
                "name": "recall_memory",
                "description": "Queries facts, constraints, and knowledge stored in the fused memory layer.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "namespace": {"type": "string"}
                    },
                    "required": ["query"]
                }
            }
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute MCP tool by name."""
        if name == "build_agent":
            raw_json = arguments.get("manifest_json", "{}")
            manifest = AgentManifest.from_json(raw_json)
            SchemaValidator.assert_valid(manifest.to_dict())
            self._runners[manifest.agent_id] = AgentRunner(manifest=manifest)
            return {"content": [{"type": "text", "text": f"Agent '{manifest.agent_id}' built and registered successfully."}]}

        elif name == "execute_agent":
            agent_id = arguments.get("agent_id")
            prompt = arguments.get("prompt")
            session_id = arguments.get("session_id")

            runner = self._runners.get(agent_id)
            if not runner:
                return {"isError": True, "content": [{"type": "text", "text": f"Agent '{agent_id}' not found."}]}

            result = await runner.run(prompt=prompt, session_id=session_id)
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "recall_memory":
            query = arguments.get("query")
            namespace = arguments.get("namespace", "default")
            block = await default_memory_manager.recall(query=query, namespace=namespace)
            return {"content": [{"type": "text", "text": block.to_system_prompt_section()}]}

        return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: '{name}'"}]}


# Global MCP Server instance
default_mcp_server = AgentMCPServer()
