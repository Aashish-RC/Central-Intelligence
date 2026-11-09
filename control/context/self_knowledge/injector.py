"""Self-Knowledge Boundary Injector (Layer 9: Context Engineering, Feature 9.17).

Bridges to Layer 4 Self-Knowledge Boundary Module to inject capability boundaries,
hard temporal knowledge cutoff dates, and active tool availability manifests.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SelfKnowledgeProfile:
    """Self-knowledge and epistemic calibration profile."""
    agent_name: str = "Central Intelligence Brain"
    agent_id: str = "ci-core-01"
    model_name: str = "ra1-hybrid"
    knowledge_cutoff_date: str = "October 2024"
    active_tools: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    financial_authority_usd: float = 0.0
    internet_access: bool = True
    sandbox_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class SelfKnowledgeInjector:
    """Formats self-knowledge and boundary context for model system frames (9.17)."""

    @classmethod
    def from_manifest(cls, manifest_data: Dict[str, Any]) -> SelfKnowledgeProfile:
        """Constructs a profile from an L4 AgentCapabilityManifest dictionary."""
        return SelfKnowledgeProfile(
            agent_name=manifest_data.get("name") or manifest_data.get("agent_name", "Central Intelligence Brain"),
            agent_id=manifest_data.get("agentId") or manifest_data.get("agent_id", "ci-core-01"),
            model_name=manifest_data.get("modelName") or manifest_data.get("model_name", "ra1-hybrid"),
            knowledge_cutoff_date=manifest_data.get("knowledgeCutoffDate") or manifest_data.get("knowledge_cutoff_date", "October 2024"),
            active_tools=manifest_data.get("registeredTools") or manifest_data.get("active_tools", []),
            capabilities=manifest_data.get("capabilities", []),
            limitations=manifest_data.get("restrictedActions") or manifest_data.get("limitations", []),
            financial_authority_usd=float(manifest_data.get("financialAuthorityUSD") or manifest_data.get("financial_authority_usd", 0.0)),
            internet_access=bool(manifest_data.get("internetAccess", True)),
            sandbox_enabled=bool(manifest_data.get("sandboxEnabled", True)),
        )

    @classmethod
    def format_block(cls, profile: SelfKnowledgeProfile) -> str:
        """Formats the profile into a grounded self-knowledge system context block."""
        tool_list = ", ".join(profile.active_tools) if profile.active_tools else "none"
        caps = ", ".join(profile.capabilities) if profile.capabilities else "general analysis and tool execution"
        limits = ", ".join(profile.limitations) if profile.limitations else "unauthorized filesystem modifications, autonomous financial transfers above limit"

        lines = [
            f"- Identity: {profile.agent_name} (ID: {profile.agent_id})",
            f"- Underlying Model: {profile.model_name}",
            f"- My knowledge cutoff is {profile.knowledge_cutoff_date}.",
            f"- I currently have access to [{tool_list}].",
            f"- Certified Capabilities: {caps}.",
            f"- Operational Limits: {limits}.",
            f"- Autonomous Financial Authority: ${profile.financial_authority_usd:.2f} USD.",
            "- Invariant: Never fabricate or hallucinate unlisted tools. State operational boundaries honestly.",
        ]
        return "\n".join(lines)
