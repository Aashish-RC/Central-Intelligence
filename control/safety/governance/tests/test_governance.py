"""
Tests for Custom AI Governance Module (Features 10.25, 10.26, 10.27, 10.28).
"""

import pytest
from unittest.mock import MagicMock

from control.safety.governance.governance_module import (
    AIGovernanceModule,
    AIRegulationMode,
    GovernanceEvaluationResult,
    PrivacyLawMode,
    ProfessionType,
    SecurityStandardMode,
    TenantGovernanceConfig,
    default_ai_governance,
)
from control.identity.tenancy.tenant_manager import TenantManager


def test_eu_ai_act_high_risk_mode_enforces_stricter_logging_and_human_oversight():
    """
    Acceptance criterion: Tenant in 'EU AI Act high-risk' mode has stricter logging + human oversight.
    """
    mock_ledger = MagicMock()
    gov = AIGovernanceModule(audit_ledger=mock_ledger)
    tenant_id = "tenant_eu_finance_01"

    config = gov.configure_tenant(
        tenant_id=tenant_id,
        ai_regulations=[AIRegulationMode.EU_AI_ACT_HIGH_RISK],
    )

    # Verify posture configuration
    assert config.is_eu_ai_act_high_risk() is True
    assert config.require_human_oversight is True
    assert config.strict_audit_logging is True

    # 1. Action without human approval -> Pending human oversight
    eval_pending = gov.evaluate_governance(
        tenant_id=tenant_id,
        action_type="autonomous_execution",
        payload={"task": "credit_scoring_model", "target_user": "u123"},
        has_human_approval=False,
    )
    assert eval_pending.allowed is False
    assert eval_pending.requires_human_oversight is True
    assert eval_pending.stricter_logging_enforced is True
    assert eval_pending.status == "pending_human_oversight"
    assert "human oversight" in eval_pending.reason.lower()
    assert eval_pending.audit_event is not None
    assert eval_pending.audit_event["regulatory_classification"] == "EU_AI_ACT_ARTICLE_14_HIGH_RISK"

    # 2. Action WITH human approval -> Approved with immutable audit trail
    eval_approved = gov.evaluate_governance(
        tenant_id=tenant_id,
        action_type="autonomous_execution",
        payload={"task": "credit_scoring_model", "target_user": "u123"},
        has_human_approval=True,
    )
    assert eval_approved.allowed is True
    assert eval_approved.status == "approved"
    assert eval_approved.stricter_logging_enforced is True
    assert eval_approved.audit_event is not None


def test_profession_rules_and_disclaimers():
    gov = AIGovernanceModule()

    # Medical tenant
    gov.configure_tenant("tenant_hospital", profession=ProfessionType.MEDICAL)
    res_med = gov.evaluate_governance("tenant_hospital", "query", {"question": "chest pain"})
    assert any("medical advice" in d.lower() for d in res_med.disclaimers_required)

    # Financial tenant
    gov.configure_tenant("tenant_wealth", profession=ProfessionType.FINANCIAL)
    res_fin = gov.evaluate_governance("tenant_wealth", "query", {"question": "stock forecast"})
    assert any("financial, investment" in d.lower() for d in res_fin.disclaimers_required)

    # Legal tenant
    gov.configure_tenant("tenant_law_firm", profession=ProfessionType.LEGAL)
    res_law = gov.evaluate_governance("tenant_law_firm", "query", {"question": "contract dispute"})
    assert any("legal advice" in d.lower() for d in res_law.disclaimers_required)


def test_privacy_laws_and_soc2_security_modes():
    gov = AIGovernanceModule()
    tenant_id = "tenant_global_enterprise"

    gov.configure_tenant(
        tenant_id=tenant_id,
        privacy_laws=[PrivacyLawMode.GDPR, PrivacyLawMode.DPDP_INDIA, PrivacyLawMode.CCPA_CPRA],
        security_standards=[SecurityStandardMode.SOC2_TYPE2, SecurityStandardMode.ISO_27001],
    )

    config = gov.get_tenant_config(tenant_id)
    assert config.strict_audit_logging is True  # Enforced by SOC 2 Type II
    assert PrivacyLawMode.GDPR in config.privacy_laws
    assert PrivacyLawMode.DPDP_INDIA in config.privacy_laws
    assert SecurityStandardMode.ISO_27001 in config.security_standards

    res = gov.evaluate_governance(tenant_id, "data_export", {"scope": "all_users"})
    assert "gdpr" in res.applicable_frameworks
    assert "dpdp_india" in res.applicable_frameworks
    assert "soc2_type2" in res.applicable_frameworks
    assert res.stricter_logging_enforced is True


def test_tenant_manager_governance_integration():
    tm = TenantManager()
    t = tm.create_tenant(
        name="Regulated Bank Tenant",
        guardrails_policy={
            "governance": {
                "high_risk": True,
                "domain": "finance",
            }
        },
    )

    # Verify tenant has governance recorded
    config = default_ai_governance.get_tenant_config(t.tenant_id)
    assert config.tenant_id == t.tenant_id
    assert config.custom_rules.get("high_risk") is True
