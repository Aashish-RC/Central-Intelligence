"""Agenta Team Workspace Adapter (Task 7.3)

Provides team-based prompt engineering, agent creation, variant management,
and evaluation environments compatible with Agenta's collaborative workspace.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentaVariant:
    """A specific prompt/parameter configuration variant for an agent."""
    variant_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    system_prompt: str = ""
    is_deployed: bool = False
    environment: Optional[str] = None  # e.g., 'staging', 'production'
    created_at: float = field(default_factory=time.time)


@dataclass
class AgentaApp:
    """An agent application within an Agenta team workspace."""
    app_id: str
    app_name: str
    workspace_id: str
    app_type: str = "chat"
    description: str = ""
    variants: Dict[str, AgentaVariant] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class AgentaWorkspace:
    """Team workspace grouping agent applications, test sets, and evaluators."""
    workspace_id: str
    name: str
    owner_id: str
    description: str = ""
    members: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class AgentaAdapter:
    """Manages team workspaces, agent definitions, variants, and deployment pipelines."""

    def __init__(self, host: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.host = host or "http://localhost:8000"
        self.api_key = api_key
        self.workspaces: Dict[str, AgentaWorkspace] = {}
        self.apps: Dict[str, AgentaApp] = {}

    def create_workspace(
        self,
        name: str,
        owner_id: str = "admin",
        description: str = "",
    ) -> AgentaWorkspace:
        """Create a new team workspace."""
        ws_id = f"ws_{len(self.workspaces) + 1}_{abs(hash(name)) % 10000}"
        ws = AgentaWorkspace(
            workspace_id=ws_id,
            name=name,
            owner_id=owner_id,
            description=description,
            members=[owner_id],
        )
        self.workspaces[ws_id] = ws
        return ws

    def create_agent(
        self,
        workspace_id: str,
        name: str,
        app_type: str = "chat",
        description: str = "",
        default_prompt: str = "You are a helpful CI assistant.",
    ) -> AgentaApp:
        """Create a new agent within a team workspace."""
        if workspace_id not in self.workspaces:
            # Auto-create workspace if not present
            self.create_workspace(name=f"Workspace_{workspace_id}", owner_id="system")

        app_id = f"app_{len(self.apps) + 1}_{abs(hash(name)) % 10000}"
        initial_variant = AgentaVariant(
            variant_name="default",
            parameters={"temperature": 0.7, "model": "gemini-2.5-flash"},
            system_prompt=default_prompt,
        )

        app = AgentaApp(
            app_id=app_id,
            app_name=name,
            workspace_id=workspace_id,
            app_type=app_type,
            description=description,
            variants={"default": initial_variant},
        )
        self.apps[app_id] = app
        return app

    def add_variant(
        self,
        app_id: str,
        variant_name: str,
        parameters: Dict[str, Any],
        system_prompt: str = "",
    ) -> AgentaVariant:
        """Register an experimental variant for an agent."""
        if app_id not in self.apps:
            raise KeyError(f"Agent application {app_id} does not exist.")

        variant = AgentaVariant(
            variant_name=variant_name,
            parameters=parameters,
            system_prompt=system_prompt,
        )
        self.apps[app_id].variants[variant_name] = variant
        return variant

    def deploy_variant(
        self,
        app_id: str,
        variant_name: str,
        environment: str = "production",
    ) -> bool:
        """Promote a variant to an active deployment environment."""
        if app_id not in self.apps or variant_name not in self.apps[app_id].variants:
            return False

        variant = self.apps[app_id].variants[variant_name]
        variant.is_deployed = True
        variant.environment = environment
        return True

    def list_agents(self, workspace_id: str) -> List[AgentaApp]:
        """List all agents belonging to a specific workspace."""
        return [app for app in self.apps.values() if app.workspace_id == workspace_id]
