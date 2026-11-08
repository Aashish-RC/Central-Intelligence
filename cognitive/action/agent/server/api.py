"""FastAPI REST Management API for Agent Layer."""

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from agent.core.manifest import AgentManifest
from agent.core.event_bus import default_event_bus
from agent.builder.schema_validator import SchemaValidator
from agent.builder.compiler import ManifestCompiler
from agent.builder.templates import CoderAgentBlueprint, ResearcherAgentBlueprint, SupportAgentBlueprint
from agent.executor.runner import AgentRunner
from agent.memory.manager import default_memory_manager
from agent.config import default_config

app = FastAPI(
    title="Pheonix Agent Layer API",
    version="1.0.0",
    description="Decoupled Unified Agent Control Plane & Execution Runtime",
)

# In-memory storage for registered agent manifests and runners
_REGISTERED_AGENTS: Dict[str, AgentManifest] = {}
_RUNNERS: Dict[str, AgentRunner] = {}


class BuildAgentRequest(BaseModel):
    graph: Optional[Dict[str, Any]] = None
    manifest: Optional[Dict[str, Any]] = None


class ExecuteAgentRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    max_steps: Optional[int] = None


@app.get("/health")
async def health_check():
    """Health status endpoint."""
    return {
        "status": "ok",
        "service": "pheonix-agent-layer",
        "version": "1.0.0",
        "registered_agents_count": len(_REGISTERED_AGENTS),
    }


@app.get("/agents/templates")
async def list_templates():
    """List available pre-packaged agent blueprints."""
    return [
        {
            "id": "coder",
            "name": "Security & Code Auditor",
            "manifest": CoderAgentBlueprint.create().to_dict(),
        },
        {
            "id": "researcher",
            "name": "Deep Research Specialist",
            "manifest": ResearcherAgentBlueprint.create().to_dict(),
        },
        {
            "id": "support",
            "name": "Customer Support Concierge",
            "manifest": SupportAgentBlueprint.create().to_dict(),
        },
    ]


@app.post("/manifest/validate")
async def validate_manifest_endpoint(manifest_data: Dict[str, Any]):
    """Validate raw manifest payload against JSONSchema and Pydantic rules."""
    is_valid, errors = SchemaValidator.validate_dict(manifest_data)
    return {
        "valid": is_valid,
        "errors": errors,
    }


@app.post("/agents/build")
async def build_agent(req: BuildAgentRequest):
    """Compile or validate and register an agent manifest."""
    try:
        if req.graph:
            manifest = ManifestCompiler.compile_graph(req.graph)
        elif req.manifest:
            manifest = SchemaValidator.assert_valid(req.manifest)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'graph' or 'manifest' must be provided in request body."
            )

        _REGISTERED_AGENTS[manifest.agent_id] = manifest
        _RUNNERS[manifest.agent_id] = AgentRunner(manifest=manifest)

        return {
            "status": "success",
            "agent_id": manifest.agent_id,
            "manifest": manifest.to_dict(),
        }

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/agents/{agent_id}/execute")
async def execute_agent(agent_id: str, req: ExecuteAgentRequest):
    """Execute an agent by ID with a given prompt."""
    if agent_id not in _RUNNERS:
        # Check if pre-packaged template matches
        if agent_id == "code-auditor-agent":
            manifest = CoderAgentBlueprint.create()
        elif agent_id == "deep-researcher-agent":
            manifest = ResearcherAgentBlueprint.create()
        elif agent_id == "customer-support-agent":
            manifest = SupportAgentBlueprint.create()
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found.")

        _REGISTERED_AGENTS[agent_id] = manifest
        _RUNNERS[agent_id] = AgentRunner(manifest=manifest)

    runner = _RUNNERS[agent_id]
    try:
        result = await runner.run(
            prompt=req.prompt,
            session_id=req.session_id,
            max_steps=req.max_steps,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/agents/{agent_id}/memory")
async def inspect_agent_memory(agent_id: str, namespace: Optional[str] = None, session_id: Optional[str] = None):
    """Inspect stored memory, facts, and working turns for an agent."""
    manifest = _REGISTERED_AGENTS.get(agent_id)
    ns = namespace or (manifest.memory.shared_namespace if manifest else "default")

    facts = default_memory_manager.facts.query_facts(namespace=ns, limit=50)
    working_turns = []
    if session_id:
        working_turns = default_memory_manager.working.get_recent_turns(session_id=session_id)

    return {
        "agent_id": agent_id,
        "namespace": ns,
        "facts_count": len(facts),
        "facts": facts,
        "session_id": session_id,
        "working_turns": working_turns,
    }


@app.get("/events")
async def list_events(run_id: Optional[str] = None):
    """List recent lifecycle events from the EventBus."""
    events = default_event_bus.get_history(run_id=run_id)
    return [e.model_dump() for e in events]
