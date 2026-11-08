"""Pre-packaged Agent Blueprint: Enterprise Customer Support."""

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


class SupportAgentBlueprint:
    """Blueprint for an Enterprise Support Agent with Parlant behavioral guardrails and customer fact memory."""

    @classmethod
    def create(cls, agent_id: str = "customer-support-agent", tenant_id: str = "tenant_default") -> AgentManifest:
        return AgentManifest(
            agent_id=agent_id,
            version="1.0.0",
            metadata=AgentMetadata(
                name="Customer Support Concierge",
                description="Resolves tier-1 and tier-2 customer inquiries with strict compliance and empathetic tone",
                tags=["support", "customer-service", "compliance", "crm"],
                author="Pheonix AI",
            ),
            runtime=RuntimeConfig(
                engine="agno",
                model="gemini-2.5-flash",
                temperature=0.1,
                max_steps=15,
                system_prompt=(
                    "You are a helpful, courteous, and accurate Customer Support Agent. "
                    "Always greet the customer politely, recall customer profile details from memory, "
                    "adhere strictly to organizational refund and privacy policies, and escalate when necessary."
                ),
            ),
            memory=MemoryConfig(
                enabled=True,
                shared_namespace=tenant_id,
                tiers=MemoryTiersConfig(
                    working_memory=True,
                    user_facts=True,
                    semantic_search=SemanticSearchConfig(
                        collection="helpdesk_kb",
                        top_k=4,
                    ),
                ),
            ),
            guardrails=GuardrailConfig(
                provider="parlant",
                ruleset_id="customer-support-guidelines",
                blocked_keywords=["guarantee 100% refund", "internal system password"],
                guidelines=[
                    "Never commit to unauthorized discounts or terms.",
                    "Protect PII: mask credit cards, phone numbers, and addresses.",
                    "Maintain a respectful and calm tone regardless of user frustration.",
                ],
            ),
            sandbox=SandboxConfig(
                required=False,
                provider="local",
            ),
            tools=[
                ToolDefinition(
                    name="knowledge_search",
                    type="builtin",
                    description="Searches internal knowledge base articles and FAQs.",
                    parameters={"query": {"type": "string"}},
                ),
                ToolDefinition(
                    name="ticket_lookup",
                    type="builtin",
                    description="Retrieves status and history of an existing support ticket.",
                    parameters={"ticket_id": {"type": "string"}},
                ),
            ],
            subagents=[],
        )
