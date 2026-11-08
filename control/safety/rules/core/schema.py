"""
Pheonix Rule Condition Matcher & Evaluation Schema
"""

from typing import Any, Dict, List, Optional
from ..models import (
    RuleCondition,
    RuleDefinition,
    RuleAction,
    RuleEvaluationResult,
    RuleScope,
)


def matches_condition(context: Dict[str, Any], cond: RuleCondition) -> bool:
    """Evaluate whether context dictionary satisfies a single condition."""
    field_val = context.get(cond.field)
    op = cond.operator.strip()
    target_val = cond.value

    if op == "==":
        return field_val == target_val
    elif op == "!=":
        return field_val != target_val
    elif op == ">":
        if field_val is None or target_val is None:
            return False
        return field_val > target_val
    elif op == "<":
        if field_val is None or target_val is None:
            return False
        return field_val < target_val
    elif op == ">=":
        if field_val is None or target_val is None:
            return False
        return field_val >= target_val
    elif op == "<=":
        if field_val is None or target_val is None:
            return False
        return field_val <= target_val
    elif op == "in":
        if isinstance(target_val, (list, tuple, set, dict, str)):
            return field_val in target_val
        return False
    elif op == "not_in":
        if isinstance(target_val, (list, tuple, set, dict, str)):
            return field_val not in target_val
        return True
    elif op == "contains":
        if isinstance(field_val, (list, tuple, set, dict, str)):
            return target_val in field_val
        return False

    return False


def matches_rule(context: Dict[str, Any], rule: RuleDefinition) -> bool:
    """A rule matches if all its conditions are satisfied (logical AND)."""
    if not rule.enabled:
        return False
    if not rule.conditions:
        return True
    return all(matches_condition(context, c) for c in rule.conditions)


def evaluate_rules(
    rules: List[RuleDefinition],
    target_scope: RuleScope,
    context: Dict[str, Any],
) -> RuleEvaluationResult:
    """
    Evaluate prioritized rules against context.
    Rules apply if rule.scope == GLOBAL or rule.scope == target_scope.
    Sorts by priority (lower number executes first).
    """
    applicable = [
        r for r in rules
        if r.enabled and (r.scope == RuleScope.GLOBAL or r.scope == target_scope)
    ]
    sorted_rules = sorted(applicable, key=lambda r: r.priority)

    for rule in sorted_rules:
        if matches_rule(context, rule):
            if rule.action == RuleAction.BLOCK:
                return RuleEvaluationResult(
                    allowed=False,
                    action=rule.action,
                    matched_rule=rule,
                    reason=rule.message or f"Action blocked by rule '{rule.name}' ({rule.rule_id})",
                )
            elif rule.action == RuleAction.REWRITE:
                rewritten = dict(context)
                if rule.rewrite_payload:
                    rewritten.update(rule.rewrite_payload)
                return RuleEvaluationResult(
                    allowed=True,
                    action=rule.action,
                    matched_rule=rule,
                    reason=rule.message or f"Context rewritten by rule '{rule.name}'",
                    rewritten_context=rewritten,
                )
            elif rule.action == RuleAction.ALLOW:
                return RuleEvaluationResult(
                    allowed=True,
                    action=rule.action,
                    matched_rule=rule,
                    reason=rule.message or f"Action permitted by rule '{rule.name}'",
                )

    # Default to ALLOW if no blocking or altering rules match
    return RuleEvaluationResult(
        allowed=True,
        action=RuleAction.ALLOW,
        matched_rule=None,
        reason="Default allow policy",
    )
