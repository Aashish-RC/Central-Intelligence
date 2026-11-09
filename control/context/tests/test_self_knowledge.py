"""Unit tests for Self-Knowledge Boundary Injector (Task 9.8, Feature 9.17)."""

import pytest
from control.context.self_knowledge.injector import SelfKnowledgeInjector, SelfKnowledgeProfile
from control.context.assembly.context_assembler import ContextAssembler


def test_self_knowledge_cutoff_and_tool_list_acceptance():
    """Task 9.8 Acceptance:
    Model context includes "My knowledge cutoff is [date]" and "I currently have access to [tool list]".
    """
    manifest_data = {
        "agentId": "sec-auditor-9",
        "name": "Security Auditor Agent",
        "modelName": "claude-3-7-sonnet",
        "knowledgeCutoffDate": "January 2025",
        "registeredTools": ["port_scan", "vuln_check", "cve_lookup"],
        "capabilities": ["static code analysis", "container vulnerability auditing"],
        "restrictedActions": ["delete_production_cluster", "modify_audit_ledger"],
        "financialAuthorityUSD": 25.0,
        "internetAccess": True,
        "sandboxEnabled": True,
    }

    profile = SelfKnowledgeInjector.from_manifest(manifest_data)
    block = SelfKnowledgeInjector.format_block(profile)

    # 1. Acceptance validations
    assert "My knowledge cutoff is January 2025." in block
    assert "I currently have access to [port_scan, vuln_check, cve_lookup]." in block
    assert "Security Auditor Agent" in block
    assert "modify_audit_ledger" in block

    # 2. Wire into ContextAssembler
    assembler = ContextAssembler()
    result = assembler.assemble(
        system_instructions=f"You are a specialized agent.\n\n<self_knowledge>\n{block}\n</self_knowledge>",
        user_input="Can you check CVE-2025-1234?",
    )

    assert "My knowledge cutoff is January 2025." in result.full_prompt
    assert "I currently have access to [port_scan, vuln_check, cve_lookup]." in result.full_prompt
    assert "<self_knowledge>" in result.full_prompt
