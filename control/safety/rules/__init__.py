"""
Pheonix Universal Rules Layer Package
"""

from .models import (
    RuleDefinition,
    RuleCondition,
    RuleScope,
    RuleAction,
    RuleEvaluationResult,
    RuleChangeEvent,
)
from .core.engine import RulesEngine
from .core.schema import matches_condition, matches_rule, evaluate_rules
from .client import RulesClient

__all__ = [
    "RulesEngine",
    "RulesClient",
    "RuleDefinition",
    "RuleCondition",
    "RuleScope",
    "RuleAction",
    "RuleEvaluationResult",
    "RuleChangeEvent",
    "matches_condition",
    "matches_rule",
    "evaluate_rules",
]
