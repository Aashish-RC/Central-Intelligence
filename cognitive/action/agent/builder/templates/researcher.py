"""Pre-packaged Agent Blueprint: Deep Researcher."""

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


class ResearcherAgentBlueprint:
    """Blueprint for a Multi-source Deep Research Agent with search and memory recall."""

    @classmethod
    def create(cls, agent_id: str = "deep-researcher-agent", tenant_id: str = "tenant_default") -> AgentManifest:
        return AgentManifest(
            agent_id=agent_id,
            version="1.0.0",
            metadata=AgentMetadata(
                name="Deep Research Specialist",
                description="Synthesizes academic, market, and technical research with citation verification",
                tags=["research", "synthesis", "search", "fact-checking"],
                author="Pheonix AI",
            ),
            runtime=RuntimeConfig(
                engine="hermes",
                model="gemini-2.5-flash",
                temperature=0.3,
                max_steps=30,
                system_prompt=(
                    "You are a thorough Deep Research Agent. Deconstruct complex research inquiries "
                    "into sub-questions, verify claims against reliable sources, recall historical "
                    "insights from memory, and synthesize cohesive reports with source citations."
                ),
            ),
            memory=MemoryConfig(
                enabled=True,
                shared_namespace=tenant_id,
                tiers=MemoryTiersConfig(
                    working_memory=True,
                    user_facts=True,
                    semantic_search=SemanticSearchConfig(
                        collection="research_papers_kb",
                        top_k=8,
                    ),
                ),
            ),
            guardrails=GuardrailConfig(
                provider="parlant",
                ruleset_id="factual-accuracy-guidelines",
                blocked_keywords=[],
                guidelines=[
                    "Provide explicit citations for factual claims.",
                    "Disclose any uncertainty or conflicting information in retrieved data.",
                ],
            ),
            sandbox=SandboxConfig(
                required=False,
                provider="local",
            ),
            tools=[
                ToolDefinition(
                    name="web_search",
                    type="builtin",
                    description="Searches the web for recent articles, documentation, and data.",
                    parameters={"query": {"type": "string"}, "num_results": {"type": "integer"}},
                ),
                ToolDefinition(
                    name="calculator",
                    type="builtin",
                    description="Performs high-precision numerical and statistical calculations.",
                    parameters={"expression": {"type": "string"}},
                ),
            ],
            subagents=[
                SubagentConfig(
                    subagent_id="fact-verifier",
                    role="Independent Verification of Statistical and Historical Claims",
                )
            ],
        )
