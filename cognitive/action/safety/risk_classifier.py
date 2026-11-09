"""Risk Classifier: Pre-execution impact analysis for agent tool and action calls.

Features: 5.22, 5.23
"""

import re
from typing import Any, Dict, List, Optional
from .models import ActionRiskAssessment, RiskLevel


class RiskClassifier:
    """Evaluates the risk profile and approval requirements of agent actions."""

    CRITICAL_KEYWORDS = [
        "drop table", "drop database", "delete from", "truncate", "rm -rf",
        "format disk", "wire transfer", "payment", "revoke credentials",
        "wipe logs", "terminate cluster", "destroy",
    ]

    HIGH_RISK_ACTIONS = [
        "execute_code", "run_command", "send_channel_message", "git_push",
        "deploy_service", "modify_iam_policy", "write_file",
    ]

    LOW_RISK_PREFIXES = [
        "read_", "get_", "list_", "inspect_", "search_", "query_", "fetch_",
    ]

    def __init__(self, approval_threshold: RiskLevel = RiskLevel.HIGH):
        self.approval_threshold = approval_threshold

    def classify_action(
        self,
        action_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionRiskAssessment:
        parameters = parameters or {}
        context = context or {}
        reasons: List[str] = []
        affected_targets: List[str] = []

        action_clean = action_name.lower().strip()
        risk_level = RiskLevel.MEDIUM

        # 1. Check for Critical keywords in parameters
        param_str = " ".join(str(v).lower() for v in parameters.values())
        for crit in self.CRITICAL_KEYWORDS:
            if crit in param_str or crit in action_clean:
                reasons.append(f"Contains critical operation marker: '{crit}'")
                risk_level = RiskLevel.CRITICAL
                break

        # 2. Check if naturally Low Risk
        if risk_level != RiskLevel.CRITICAL:
            if any(action_clean.startswith(prefix) for prefix in self.LOW_RISK_PREFIXES):
                risk_level = RiskLevel.LOW
                reasons.append("Read-only / inspection action")
            elif any(high in action_clean for high in self.HIGH_RISK_ACTIONS):
                # Inspect parameters for destructive paths
                path = str(parameters.get("path", "")).lower()
                if "scratch" in path or "tmp" in path or "temp" in path:
                    risk_level = RiskLevel.MEDIUM
                    reasons.append("Write scoped to disposable scratchpad")
                else:
                    risk_level = RiskLevel.HIGH
                    reasons.append(f"Mutating external action '{action_name}'")

        # Extract affected targets
        if "path" in parameters:
            affected_targets.append(str(parameters["path"]))
        if "channel" in parameters:
            affected_targets.append(f"channel:{parameters['channel']}")
        if "url" in parameters:
            affected_targets.append(str(parameters["url"]))

        # Determine if approval is required
        level_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        requires_approval = level_order.index(risk_level) >= level_order.index(self.approval_threshold)

        is_reversible = risk_level != RiskLevel.CRITICAL

        return ActionRiskAssessment(
            action_name=action_name,
            risk_level=risk_level,
            requires_approval=requires_approval,
            reasons=reasons,
            affected_targets=affected_targets,
            is_reversible=is_reversible,
            blast_radius_summary=f"Risk: {risk_level.value.upper()} | Targets: {len(affected_targets)}",
        )
