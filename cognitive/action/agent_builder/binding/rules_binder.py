"""Rules Binder: Dynamically binds safety rules and permission modes to synthesized agents."""

from typing import List, Optional
from ..core.interfaces import BaseRulesBinder
from ..core.models import AgentRulesBinding


class RulesBinder(BaseRulesBinder):
    """Enforces organizational rules and permission boundaries on compiled agents."""

    def bind_rules(
        self, description_text: str, requested_mode: Optional[str] = None
    ) -> AgentRulesBinding:
        text = description_text.lower()

        # Determine permission mode
        if requested_mode in ("always_ask", "ask_on_changes", "auto_review"):
            perm_mode = requested_mode
        elif any(w in text for w in ("delete", "purchase", "execute", "modify", "write", "change")):
            perm_mode = "ask_on_changes"
        else:
            perm_mode = "auto_review"

        # Mandatory baseline rules
        rules: List[str] = [
            "rule_deny_secret_leakage",
            "rule_prevent_path_traversal",
            "rule_token_budget_guard",
        ]

        # Domain specific rule bindings
        if any(w in text for w in ("code", "python", "script", "execute")):
            rules.append("rule_sandbox_ephemeral_cleanup")

        if any(w in text for w in ("browse", "web", "scrape")):
            rules.append("rule_polite_scraping_compliance")

        return AgentRulesBinding(
            permission_mode=perm_mode,
            active_rules=rules,
            sandbox_required=True,
            max_cost_per_run_usd=2.50,
        )
