"""Pre-packaged Agent Blueprint: Coder & Security Auditor."""

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


class CoderAgentBlueprint:
    """Blueprint for a Security & Code Auditor Agent with microVM sandbox and PR tools."""

    @classmethod
    def create(cls, agent_id: str = "code-auditor-agent", tenant_id: str = "tenant_default") -> AgentManifest:
        return AgentManifest(
            agent_id=agent_id,
            version="1.0.0",
            metadata=AgentMetadata(
                name="Security & Code Auditor",
                description="Reviews PRs, tests vulnerabilities in a sandbox, and reports findings",
                tags=["coding", "security", "audit", "sandbox"],
                author="Pheonix AI",
            ),
            runtime=RuntimeConfig(
                engine="agno",
                model="gemini-2.5-flash",
                temperature=0.2,
                max_steps=25,
                system_prompt=(
                    "You are an expert Security & Code Auditor. You rigorously inspect code for "
                    "vulnerabilities (OWASP Top 10, memory leaks, concurrency bugs), execute tests "
                    "in the isolated sandbox, and produce structured, actionable remediation reports."
                ),
            ),
            memory=MemoryConfig(
                enabled=True,
                shared_namespace=tenant_id,
                tiers=MemoryTiersConfig(
                    working_memory=True,
                    user_facts=True,
                    semantic_search=SemanticSearchConfig(
                        collection="codebase_kb",
                        top_k=5,
                    ),
                ),
            ),
            guardrails=GuardrailConfig(
                provider="parlant",
                ruleset_id="enterprise-compliance-rules",
                blocked_keywords=["rm -rf /", "DROP DATABASE", "format c:"],
                guidelines=[
                    "Never output plain-text credentials or API secrets.",
                    "Always run unverified code inside the sandbox container.",
                ],
            ),
            sandbox=SandboxConfig(
                required=True,
                provider="e2b",
                template="python-3.11-data-science",
                timeout_seconds=60,
            ),
            tools=[
                ToolDefinition(
                    name="run_test_suite",
                    type="sandbox_command",
                    command="pytest tests/",
                    description="Executes the project test suite inside the isolated microVM sandbox.",
                ),
                ToolDefinition(
                    name="file_read",
                    type="builtin",
                    description="Reads source files from the workspace.",
                    parameters={"path": {"type": "string"}},
                ),
                ToolDefinition(
                    name="file_write",
                    type="builtin",
                    description="Writes or patches files in the workspace or sandbox.",
                    parameters={"path": {"type": "string"}, "content": {"type": "string"}},
                ),
            ],
            subagents=[
                SubagentConfig(
                    subagent_id="vulnerability-scanner",
                    role="Static Analysis & Dependency Vulnerability Scanner",
                )
            ],
        )
