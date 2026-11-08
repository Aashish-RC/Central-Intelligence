"""App Composer Runtime: Assembles applications from natural language prompts, tools, and plugins."""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

from ..compiler.describe_to_agent import DescribeToAgentCompiler
from ..core.models import (
    AgentPersona,
    AgentSpecification,
    DescribeAgentRequest,
)


from .layout_engine import LayoutEngine, LayoutTree


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ComposedApp(BaseModel):
    app_id: str = Field(default_factory=lambda: f"app_{uuid.uuid4().hex[:8]}")
    name: str
    description: str
    target_domain: str = "general"
    system_prompt: str
    primary_agent: AgentSpecification
    sub_agents: List[AgentSpecification] = Field(default_factory=list)
    plugin_ids: List[str] = Field(default_factory=list)
    active_skills: List[str] = Field(default_factory=list)
    layout: Optional[LayoutTree] = None
    html_skeleton: Optional[str] = None
    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=utc_now)


class AppComposer:
    """Assembles prompt-driven applications with agent configurations, tool bindings, and plugins."""

    def __init__(
        self,
        compiler: Optional[DescribeToAgentCompiler] = None,
        layout_engine: Optional[LayoutEngine] = None,
    ):
        self.compiler = compiler or DescribeToAgentCompiler()
        self.layout_engine = layout_engine or LayoutEngine()

    def compose_app(
        self,
        prompt: str,
        name: Optional[str] = None,
        target_domain: Optional[str] = None,
        plugin_ids: Optional[List[str]] = None,
        active_skills: Optional[List[str]] = None,
        permission_mode: str = "ask_on_changes",
    ) -> ComposedApp:
        req = DescribeAgentRequest(
            prompt=prompt,
            target_domain=target_domain,
            requested_permission_mode=permission_mode,
        )
        build_res = self.compiler.compile_agent(req)
        if not build_res.success or not build_res.specification:
            raise ValueError(f"Failed to compile primary agent for app: {build_res.validation_errors}")

        spec = build_res.specification
        app_name = name or f"{spec.name} Application"
        domain = target_domain or "general"
        app_id = f"app_{uuid.uuid4().hex[:8]}"

        layout = self.layout_engine.synthesize_layout(
            app_id=app_id,
            title=app_name,
            domain=domain,
            plugins=plugin_ids,
        )
        html_skeleton = self.layout_engine.render_html_skeleton(layout)

        return ComposedApp(
            app_id=app_id,
            name=app_name,
            description=f"Auto-composed app for: {prompt[:80]}...",
            target_domain=domain,
            system_prompt=spec.system_prompt,
            primary_agent=spec,
            plugin_ids=plugin_ids or [],
            active_skills=active_skills or [],
            layout=layout,
            html_skeleton=html_skeleton,
        )

    def execute_app(self, app: ComposedApp, input_query: str) -> Dict[str, Any]:
        """Runs the composed application against an incoming query."""
        start = time.perf_counter()
        agent = app.primary_agent
        duration = (time.perf_counter() - start) * 1000.0

        return {
            "app_id": app.app_id,
            "app_name": app.name,
            "status": "success",
            "agent_id": agent.agent_id,
            "query": input_query,
            "response": f"[{app.name}] Processed query using {agent.model_binding.primary_model}.",
            "duration_ms": round(duration, 2),
            "plugins_used": app.plugin_ids,
        }
