"""
Custom AI Governance Framework (Features 10.25, 10.26, 10.27, 10.28).
Clean Apache-2.0 implementation replacing AGPL VerifyWise.

Features:
- 10.25: Governance rule sets per tenant, profession (legal, medical, financial), and app scope.
- 10.26: Privacy-law modes (GDPR, India DPDP, CCPA/CPRA).
- 10.27: Security-standard modes (SOC 2 Type II, ISO 27001).
- 10.28: AI-regulation modes (EU AI Act high-risk, ISO 42001, NIST AI RMF).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("control.safety.governance")


class PrivacyLawMode(str, Enum):
    GDPR = "gdpr"                     # EU General Data Protection Regulation
    DPDP_INDIA = "dpdp_india"         # India Digital Personal Data Protection Act 2023
    CCPA_CPRA = "ccpa_cpra"           # California Consumer Privacy Act / CPRA


class SecurityStandardMode(str, Enum):
    SOC2_TYPE2 = "soc2_type2"         # AICPA SOC 2 Type II (continuous audit logging, access controls)
    ISO_27001 = "iso_27001"           # ISO/IEC 27001 Information Security Management


class AIRegulationMode(str, Enum):
    EU_AI_ACT_HIGH_RISK = "eu_ai_act_high_risk"       # EU AI Act Articles 6, 9-15: Human oversight + immutable logs
    EU_AI_ACT_TRANSPARENCY = "eu_ai_act_transparency" # EU AI Act Article 50: AI transparency disclosures
    ISO_42001 = "iso_42001"                           # ISO/IEC 42001 AI Management System
    NIST_AI_RMF = "nist_ai_rmf"                       # NIST AI Risk Management Framework 1.0


class ProfessionType(str, Enum):
    LEGAL = "legal"                   # Legal privilege, citation hallucination check
    MEDICAL = "medical"               # HIPAA / PHI compliance, clinical disclaimer
    FINANCIAL = "financial"           # SEC/FINRA compliance, financial advice disclaimer
    ENGINEERING = "engineering"       # Code vulnerability, license compliance


@dataclass
class TenantGovernanceConfig:
    """Configured compliance and regulatory posture for a tenant."""
    tenant_id: str
    profession: Optional[ProfessionType] = None
    app_scope: str = "default"
    privacy_laws: Set[PrivacyLawMode] = field(default_factory=set)
    security_standards: Set[SecurityStandardMode] = field(default_factory=set)
    ai_regulations: Set[AIRegulationMode] = field(default_factory=set)
    require_human_oversight: bool = False
    strict_audit_logging: bool = False
    custom_rules: Dict[str, Any] = field(default_factory=dict)
    retention_days: int = 365

    def is_eu_ai_act_high_risk(self) -> bool:
        return AIRegulationMode.EU_AI_ACT_HIGH_RISK in self.ai_regulations


@dataclass
class GovernanceEvaluationResult:
    """Assessment of an action or generation under applicable governance frameworks."""
    allowed: bool
    requires_human_oversight: bool
    stricter_logging_enforced: bool
    status: str  # "approved", "pending_human_oversight", "blocked"
    applicable_frameworks: List[str] = field(default_factory=list)
    disclaimers_required: List[str] = field(default_factory=list)
    audit_event: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class AIGovernanceModule:
    """
    Orchestrates tenant, professional, and statutory AI governance rules.
    """

    def __init__(self, tenant_manager: Optional[Any] = None, audit_ledger: Optional[Any] = None):
        self._tenant_manager = tenant_manager
        self._audit_ledger = audit_ledger
        self._configs: Dict[str, TenantGovernanceConfig] = {}

    def _get_tenant_manager(self) -> Any:
        if self._tenant_manager is None:
            try:
                from control.identity.tenancy.tenant_manager import default_tenant_manager
                self._tenant_manager = default_tenant_manager
            except ImportError:
                pass
        return self._tenant_manager

    def _get_audit_ledger(self) -> Any:
        if self._audit_ledger is None:
            try:
                from control.safety.audit.ledger import default_audit_ledger
                self._audit_ledger = default_audit_ledger
            except ImportError:
                pass
        return self._audit_ledger

    def configure_tenant(
        self,
        tenant_id: str,
        profession: Optional[ProfessionType] = None,
        app_scope: str = "default",
        privacy_laws: Optional[List[PrivacyLawMode]] = None,
        security_standards: Optional[List[SecurityStandardMode]] = None,
        ai_regulations: Optional[List[AIRegulationMode]] = None,
        require_human_oversight: Optional[bool] = None,
        strict_audit_logging: Optional[bool] = None,
        custom_rules: Optional[Dict[str, Any]] = None,
    ) -> TenantGovernanceConfig:
        """Configures or updates regulatory posture for a specific tenant."""
        p_laws = set(privacy_laws or [])
        sec_stds = set(security_standards or [])
        ai_regs = set(ai_regulations or [])

        # Feature 10.28: EU AI Act High-Risk automatically mandates human oversight and stricter audit logging
        is_high_risk = AIRegulationMode.EU_AI_ACT_HIGH_RISK in ai_regs
        is_soc2 = SecurityStandardMode.SOC2_TYPE2 in sec_stds

        human_oversight = require_human_oversight if require_human_oversight is not None else is_high_risk
        strict_logging = strict_audit_logging if strict_audit_logging is not None else (is_high_risk or is_soc2)

        config = TenantGovernanceConfig(
            tenant_id=tenant_id,
            profession=profession,
            app_scope=app_scope,
            privacy_laws=p_laws,
            security_standards=sec_stds,
            ai_regulations=ai_regs,
            require_human_oversight=human_oversight,
            strict_audit_logging=strict_logging,
            custom_rules=custom_rules or {},
        )
        self._configs[tenant_id] = config

        # Sync with L12 Tenancy
        tm = self._get_tenant_manager()
        if tm and hasattr(tm, "get_tenant"):
            try:
                t = tm.get_tenant(tenant_id)
                t.guardrails_policy["governance"] = {
                    "profession": profession.value if profession else None,
                    "ai_regulations": [r.value for r in ai_regs],
                    "privacy_laws": [p.value for p in p_laws],
                    "security_standards": [s.value for s in sec_stds],
                    "require_human_oversight": human_oversight,
                    "strict_audit_logging": strict_logging,
                }
            except Exception:
                pass

        logger.info(
            "Configured governance for tenant '%s': regulations=%s, human_oversight=%s, strict_logging=%s",
            tenant_id,
            [r.value for r in ai_regs],
            human_oversight,
            strict_logging,
        )
        return config

    def get_tenant_config(self, tenant_id: str) -> TenantGovernanceConfig:
        """Retrieves tenant governance config, creating default if not yet initialized."""
        if tenant_id not in self._configs:
            self._configs[tenant_id] = TenantGovernanceConfig(tenant_id=tenant_id)
        return self._configs[tenant_id]

    def evaluate_governance(
        self,
        tenant_id: str,
        action_type: str,
        payload: Dict[str, Any],
        has_human_approval: bool = False,
    ) -> GovernanceEvaluationResult:
        """
        Enforces governance rules for tenant actions (Features 10.25, 10.26, 10.27, 10.28).
        Acceptance: Tenant in 'EU AI Act high-risk' mode has stricter logging + human oversight.
        """
        config = self.get_tenant_config(tenant_id)
        frameworks: List[str] = []
        disclaimers: List[str] = []

        # 1. AI Regulations (Feature 10.28)
        requires_human_oversight = config.require_human_oversight
        stricter_logging = config.strict_audit_logging

        for reg in config.ai_regulations:
            frameworks.append(reg.value)
            if reg == AIRegulationMode.EU_AI_ACT_HIGH_RISK:
                requires_human_oversight = True
                stricter_logging = True
            elif reg == AIRegulationMode.EU_AI_ACT_TRANSPARENCY:
                disclaimers.append("This content was generated with the assistance of Artificial Intelligence.")

        # 2. Professional Disclaimers (Feature 10.25)
        if config.profession == ProfessionType.MEDICAL:
            disclaimers.append("Notice: This information is for educational purposes and is not a substitute for professional medical advice or diagnosis.")
            frameworks.append("HIPAA/Medical_Guidance")
        elif config.profession == ProfessionType.FINANCIAL:
            disclaimers.append("Notice: This material does not constitute financial, investment, or tax advice.")
            frameworks.append("FINRA_SEC/Financial_Guidance")
        elif config.profession == ProfessionType.LEGAL:
            disclaimers.append("Notice: This analysis does not constitute legal advice or establish an attorney-client relationship.")
            frameworks.append("Legal_Professional_Ethics")

        # 3. Privacy Laws (Feature 10.26)
        for law in config.privacy_laws:
            frameworks.append(law.value)

        # 4. Security Standards (Feature 10.27)
        for sec in config.security_standards:
            frameworks.append(sec.value)

        # Determine approval status based on Human Oversight requirements
        status = "approved"
        reason = "Complies with applicable governance frameworks."
        if requires_human_oversight and not has_human_approval and action_type in ("autonomous_execution", "high_risk_decision", "model_dispatch"):
            status = "pending_human_oversight"
            reason = "EU AI Act High-Risk / Tenant Policy requires human oversight before final execution."

        # Audit Event creation
        audit_event = None
        if stricter_logging:
            audit_event = {
                "timestamp": time.time(),
                "tenant_id": tenant_id,
                "action_type": action_type,
                "status": status,
                "requires_human_oversight": requires_human_oversight,
                "has_human_approval": has_human_approval,
                "governance_frameworks": frameworks,
                "regulatory_classification": "EU_AI_ACT_ARTICLE_14_HIGH_RISK" if config.is_eu_ai_act_high_risk() else "STANDARD_AUDIT",
                "payload_summary": {k: type(v).__name__ for k, v in payload.items()},
            }
            # Record in Ledger if available
            ledger = self._get_audit_ledger()
            if ledger and hasattr(ledger, "record"):
                try:
                    ledger.record(
                        event_type="governance_evaluation",
                        actor=f"tenant:{tenant_id}",
                        details=str(audit_event),
                        severity="info" if status == "approved" else "warning",
                    )
                except Exception:
                    pass

        return GovernanceEvaluationResult(
            allowed=(status == "approved"),
            requires_human_oversight=requires_human_oversight,
            stricter_logging_enforced=stricter_logging,
            status=status,
            applicable_frameworks=frameworks,
            disclaimers_required=disclaimers,
            audit_event=audit_event,
            reason=reason,
        )


# Global default singleton
default_ai_governance = AIGovernanceModule()

